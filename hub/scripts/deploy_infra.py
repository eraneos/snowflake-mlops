"""Deploy hub-owned Snowflake infrastructure.

Runs the account-level bootstrap (database, role, warehouse, compute pool)
followed by the shared-schema bootstrap (`SHARED_DATA`, `FEATURE_STORE_<ENV>`,
`MODEL_REGISTRY_<ENV>` for DEV/STAGING/PROD). Idempotent.

Per the migration plan this is the entry point invoked by
`make -C hub deploy-infra` (Makefile arrives in migration step 10). The
account-level steps require ACCOUNTADMIN; the bootstrap-vs-ops handoff is
open under ADR-0013 (proposed).
"""

import logging
from pathlib import Path
import sys

from hub.core.session import create_session
from hub.infra.account.bootstrap import bootstrap_account
from hub.infra.schemas.shared import bootstrap_shared_schemas

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    if not Path(".env").exists():
        logger.error(".env file not found. Create it from .env.example.")
        sys.exit(1)

    session = create_session(role="ACCOUNTADMIN")
    try:
        bootstrap_account(session)
        bootstrap_shared_schemas(session)
    finally:
        session.close()

    logger.info("Hub infrastructure deploy complete.")


if __name__ == "__main__":
    main()
