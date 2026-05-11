"""Snowpark session creation for hub deploy operations.

Duplicated from project-side per ADR-0001 / ADR-0003. The hub variant does
not pin a schema in the connection (hub bootstrap creates schemas; it does
not target a particular one). Otherwise mirrors the legacy session helper.
"""

import logging
import os
from pathlib import Path

from snowflake.snowpark import Session
from snowflake.snowpark.context import get_active_session

from hub.core.config import infra_config
from hub.core.credentials import get_credentials

logger = logging.getLogger(__name__)


def get_session() -> Session:
    try:
        return get_active_session()
    except Exception:
        return create_session()


def create_session(schema: str | None = None, role: str | None = None) -> Session:
    creds = get_credentials()
    connection_params = creds.get_connection_params(
        warehouse=infra_config.warehouse.name,
        database=infra_config.database.name,
        role=role or infra_config.role.name,
        schema=schema,
    )

    if creds.authenticator.lower() in ("jwt", "snowflake_jwt"):
        _attach_jwt_key(connection_params)

    logger.info(
        "Connecting to Snowflake account %s as %s",
        connection_params["account"],
        connection_params["user"],
    )
    return Session.builder.configs(connection_params).create()


def _attach_jwt_key(connection_params: dict) -> None:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import serialization

    connection_params["authenticator"] = "snowflake_jwt"

    private_key_path = os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH")
    private_key_content = os.getenv("SNOWFLAKE_PRIVATE_KEY")
    private_key_passphrase = os.getenv("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE")
    passphrase_bytes = private_key_passphrase.encode() if private_key_passphrase else None

    if private_key_path:
        private_key_pem = Path(private_key_path).read_bytes()
    elif private_key_content:
        private_key_pem = private_key_content.encode()
    else:
        msg = "SNOWFLAKE_PRIVATE_KEY_PATH or SNOWFLAKE_PRIVATE_KEY required for JWT auth"
        raise ValueError(msg)

    private_key_obj = serialization.load_pem_private_key(
        private_key_pem, password=passphrase_bytes, backend=default_backend()
    )
    connection_params["private_key"] = private_key_obj.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
