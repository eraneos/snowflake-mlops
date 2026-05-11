"""Snowflake credentials loaded from environment variables.

Duplicated from hub-side per ADR-0001 (mock_data does not import from hub or
projects) and ADR-0003 (each component owns a minimal `core/`). Candidate for
centralization once ADR-0020 lands.
"""

import os
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv(override=True)


class SnowflakeCredentials(BaseModel):
    account: str
    user: str
    password: str | None = None
    token: str | None = None
    authenticator: str = "externalbrowser"

    def get_connection_params(
        self, warehouse: str, database: str, role: str, schema: str | None = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "account": self.account,
            "user": self.user,
            "warehouse": warehouse,
            "database": database,
            "role": role,
            "authenticator": self.authenticator,
        }
        if schema is not None:
            params["schema"] = schema
        if self.authenticator == "snowflake" and self.password:
            params["password"] = self.password
        elif self.authenticator == "oauth" and self.token:
            params["token"] = self.token
        return {k: v for k, v in params.items() if v is not None}


def get_credentials() -> SnowflakeCredentials:
    account = os.getenv("SNOWFLAKE_ACCOUNT")
    user = os.getenv("SNOWFLAKE_USER")
    if not account or not user:
        msg = "SNOWFLAKE_ACCOUNT and SNOWFLAKE_USER must be set in .env"
        raise ValueError(msg)
    return SnowflakeCredentials(
        account=account,
        user=user,
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        token=os.getenv("SNOWFLAKE_OAUTH_TOKEN"),
        authenticator=os.getenv("SNOWFLAKE_AUTHENTICATOR", "externalbrowser"),
    )
