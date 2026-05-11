"""Snowpark session management for the PUDO project.

Loads credentials from ``.env`` and platform resource names from
``projects/pudo/config/infrastructure.yaml``. Per ADR-0004 the session lands in
the project schema (``PUDO_<ENV>``); callers can override per query.
"""

import logging
import os
from pathlib import Path

from snowflake.snowpark import Session
from snowflake.snowpark.context import get_active_session

from pudo.core.config.infrastructure import config as infra
from pudo.core.credentials import get_credentials
from pudo.core.environment import detect_environment, get_project_schema

logger = logging.getLogger(__name__)


def get_session() -> Session:
    """Get Snowflake session - tries active session first, then creates new one.

    This is the recommended way to get a session as it works both:
    - In Snowflake (uses active session from stored procedure/UDF context)
    - Locally (creates new session from config)

    Returns:
        Session: Active or newly created Snowpark session

    Example:
        >>> session = get_session()
        >>> result = session.sql("SELECT CURRENT_USER()").collect()
    """
    try:
        # Try to get active session (when running in Snowflake)
        return get_active_session()
    except Exception:
        # Create new session (when running locally or in CI/CD)
        return create_session()


def create_session() -> Session:
    """Create new Snowflake session from unified config.

    Loads configuration from:
    1. config/infrastructure.yaml (infrastructure names)
    2. Git branch detection (environment)
    3. config/{env}.yaml (environment overrides)
    4. .env file (credentials)

    Supports multiple authentication methods:
    - externalbrowser (SSO) - Default
    - snowflake (username/password)
    - oauth (OAuth token)
    - jwt (Key pair authentication)

    Returns:
        Session: New Snowpark session

    Raises:
        ValueError: If required credentials are missing
        Exception: If connection fails

    Example:
        >>> session = create_session()
        >>> session.sql("SELECT CURRENT_DATABASE()").collect()
    """
    # Load credentials and environment
    creds = get_credentials()
    environment = detect_environment()
    schema = get_project_schema(environment)

    # Get connection parameters from credentials
    connection_params = creds.get_connection_params(
        warehouse=infra.warehouse.name,
        database=infra.database.name,
        schema=schema,
        role=infra.role.name,
    )

    # Handle JWT authentication if configured
    authenticator = creds.authenticator.lower()

    if authenticator in ["jwt", "snowflake_jwt"]:
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import serialization

        connection_params["authenticator"] = "snowflake_jwt"

        # Load private key
        private_key_path = os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH")
        private_key_content = os.getenv("SNOWFLAKE_PRIVATE_KEY")
        private_key_passphrase = os.getenv("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE")

        # Convert passphrase to bytes if provided
        passphrase_bytes = private_key_passphrase.encode() if private_key_passphrase else None

        # Load private key from file or content
        if private_key_path:
            with Path(private_key_path).open("rb") as key_file:
                private_key_pem = key_file.read()
            logger.info(f"🔐 Using JWT authentication with key file: {private_key_path}")
        elif private_key_content:
            private_key_pem = private_key_content.encode()
            logger.info("🔐 Using JWT authentication with provided key content")
        else:
            msg = "SNOWFLAKE_PRIVATE_KEY_PATH or SNOWFLAKE_PRIVATE_KEY required for JWT auth"
            raise ValueError(msg)

        # Convert PEM to DER format (Snowflake requires DER format)
        try:
            private_key_obj = serialization.load_pem_private_key(
                private_key_pem, password=passphrase_bytes, backend=default_backend()
            )
            # Serialize to DER format (unencrypted)
            private_key_der = private_key_obj.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            connection_params["private_key"] = private_key_der
        except Exception as e:
            logger.error(f"Failed to load/convert private key: {e}")
            msg = f"Invalid private key format: {e}"
            raise ValueError(msg) from e

    # Log connection attempt
    logger.info(f"🔌 Connecting to Snowflake account: {connection_params['account']}")
    logger.info(f"👤 User: {connection_params['user']}")
    logger.info(f"🏢 Warehouse: {connection_params.get('warehouse', 'N/A')}")
    logger.info(f"🗄️  Database: {connection_params.get('database', 'N/A')}")
    logger.info(f"📁 Schema: {connection_params.get('schema', 'N/A')}")
    logger.info(f"🌍 Environment: {environment}")

    # Log auth method
    auth_method_display = {
        "externalbrowser": "🔐 Using external browser authentication (SSO)",
        "oauth": "🔐 Using OAuth authentication",
        "snowflake_jwt": "🔐 Using JWT (key pair) authentication",
        "snowflake": "🔐 Using username/password authentication",
    }
    logger.info(auth_method_display.get(authenticator, f"🔐 Using {authenticator} authentication"))

    try:
        # Create session
        session = Session.builder.configs(connection_params).create()

        # Configure for custom packages
        _configure_session_for_custom_packages(session)

        logger.info("✅ Connected successfully!")
        return session

    except Exception as e:
        logger.error(f"❌ Failed to connect to Snowflake: {e!s}")

        # Provide helpful error messages
        if authenticator == "externalbrowser":
            logger.info("💡 External browser authentication tips:")
            logger.info("   - Make sure your browser opens for authentication")
            logger.info("   - Check if you're logged into the correct Snowflake account")
            logger.info("   - Verify your user has the correct role assigned")
        elif authenticator == "oauth":
            logger.info("💡 OAuth authentication tips:")
            logger.info("   - Verify your OAuth token is valid and not expired")
            logger.info("   - Check if the token has the correct scopes")
        elif authenticator in ["jwt", "snowflake_jwt"]:
            logger.info("💡 JWT authentication tips:")
            logger.info("   - Verify your private key file path is correct")
            logger.info("   - Check if the private key is properly formatted")
            logger.info("   - Ensure the public key is registered with your Snowflake user")
        else:
            logger.info("💡 Username/password authentication tips:")
            logger.info("   - Verify your username and password are correct")
            logger.info("   - Check if your account identifier is correct")

        raise


def _configure_session_for_custom_packages(session: Session) -> None:
    """Configure session to allow custom packages for stored procedures/UDFs."""
    try:
        session.custom_package_usage_config = {
            "enabled": True,
            "force_push": False,
            "cache_path": "/tmp/snowflake_packages",  # noqa: S108
        }
        logger.info("✅ Configured session for custom packages")
    except Exception as e:
        logger.warning(f"⚠️  Could not configure custom packages: {e}")


def test_connection(session: Session) -> bool:
    """Test Snowflake connection and display session info.

    Args:
        session: Snowpark session to test

    Returns:
        bool: True if connection is successful, False otherwise

    Example:
        >>> session = create_session()
        >>> if test_connection(session):
        ...     print("Connection OK")
    """
    try:
        # Test basic connectivity
        result = session.sql("SELECT CURRENT_VERSION()").collect()
        version = result[0][0]

        logger.info("✅ Snowflake connection test passed!")
        logger.info(f"📊 Snowflake Version: {version}")

        # Get session information
        info = get_session_info(session)
        logger.info(f"🏢 Account: {info.get('account', 'N/A')}")
        logger.info(f"👤 User: {info.get('user', 'N/A')}")
        logger.info(f"🎭 Role: {info.get('role', 'N/A')}")
        logger.info(f"🏭 Warehouse: {info.get('warehouse', 'N/A')}")
        logger.info(f"🗄️  Database: {info.get('database', 'N/A')}")
        logger.info(f"📁 Schema: {info.get('schema', 'N/A')}")

        return True

    except Exception as e:
        logger.error(f"❌ Connection test failed: {e!s}")
        return False


def get_session_info(session: Session) -> dict[str, str | None]:
    """Get information about current Snowflake session.

    Args:
        session: Snowpark session to inspect

    Returns:
        dict: Session information (account, user, role, warehouse, database, schema, version)

    Example:
        >>> session = get_session()
        >>> info = get_session_info(session)
        >>> print(info["database"])
        'OSS_SF_MLOPS'
    """
    info_queries = {
        "account": "SELECT CURRENT_ACCOUNT()",
        "user": "SELECT CURRENT_USER()",
        "role": "SELECT CURRENT_ROLE()",
        "warehouse": "SELECT CURRENT_WAREHOUSE()",
        "database": "SELECT CURRENT_DATABASE()",
        "schema": "SELECT CURRENT_SCHEMA()",
        "version": "SELECT CURRENT_VERSION()",
    }

    session_info = {}
    for key, query in info_queries.items():
        try:
            result = session.sql(query).collect()
            session_info[key] = result[0][0] if result else None
        except Exception:
            session_info[key] = None

    return session_info
