"""Snowflake credentials management.

Loads Snowflake connection credentials from environment variables (.env file).
"""

import os
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel

# Load .env file
load_dotenv(override=True)


class SnowflakeCredentials(BaseModel):
    """Snowflake credentials from .env file."""

    account: str
    user: str
    password: str | None = None
    token: str | None = None
    authenticator: str = "externalbrowser"

    def get_connection_params(self, warehouse: str, database: str, schema: str, role: str) -> dict[str, Any]:
        """Get Snowpark connection parameters.

        Args:
            warehouse: Warehouse name
            database: Database name
            schema: Schema name
            role: Role name

        Returns:
            Dictionary of connection parameters for Snowpark

        Example:
            >>> creds = get_credentials()
            >>> params = creds.get_connection_params("WH", "DB", "SCHEMA", "ROLE")
            >>> session = Session.builder.configs(params).create()
        """
        params = {
            "account": self.account,
            "user": self.user,
            "warehouse": warehouse,
            "database": database,
            "schema": schema,
            "role": role,
            "authenticator": self.authenticator,
        }

        # Add auth-specific params
        if self.authenticator == "snowflake" and self.password:
            params["password"] = self.password
        elif self.authenticator == "oauth" and self.token:
            params["token"] = self.token

        return {k: v for k, v in params.items() if v is not None}


def get_credentials() -> SnowflakeCredentials:
    """Load Snowflake credentials from environment variables.

    Required environment variables:
    - SNOWFLAKE_ACCOUNT: Snowflake account identifier
    - SNOWFLAKE_USER: Snowflake user name

    Optional environment variables:
    - SNOWFLAKE_PASSWORD: Password (for snowflake authenticator)
    - SNOWFLAKE_OAUTH_TOKEN: OAuth token (for oauth authenticator)
    - SNOWFLAKE_AUTHENTICATOR: Authentication method (default: externalbrowser)

    Returns:
        SnowflakeCredentials object

    Raises:
        ValueError: If required environment variables are not set

    Example:
        >>> creds = get_credentials()
        >>> print(creds.account)
        'my-account'
    """
    account = os.getenv("SNOWFLAKE_ACCOUNT")
    user = os.getenv("SNOWFLAKE_USER")

    if not account or not user:
        msg = "SNOWFLAKE_ACCOUNT and SNOWFLAKE_USER must be set in .env file"
        raise ValueError(msg)

    return SnowflakeCredentials(
        account=account,
        user=user,
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        token=os.getenv("SNOWFLAKE_OAUTH_TOKEN"),
        authenticator=os.getenv("SNOWFLAKE_AUTHENTICATOR", "externalbrowser"),
    )
