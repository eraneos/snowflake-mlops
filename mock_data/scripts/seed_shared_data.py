#!/usr/bin/env python3
"""Create the four PUDO source tables in `SHARED_DATA` and populate them.

The `SHARED_DATA` schema itself is created by hub (`make -C hub deploy-infra`,
per ADR-0004). This script only creates the tables and seeds them.

Run wrapped via `make -C mock_data seed-shared-data` (per ADR-0012).
"""

import logging
from pathlib import Path
import subprocess
import sys

from pudo_data.core.config import infra_config
from pudo_data.core.session import create_session
from pudo_data.core.sql_utils import execute_sql_file

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def setup_shared_data(sql_dir: Path) -> None:
    db = infra_config.database.name
    wh = infra_config.warehouse.name
    role = infra_config.role.name
    shared_schema = infra_config.shared_data.schema_name

    logger.info("🚀 Setting up tables in %s.%s", db, shared_schema)
    logger.info("  Warehouse: %s", wh)
    logger.info("  Role:      %s", role)

    logger.info("🔐 Connecting to Snowflake with role %s...", role)
    session = create_session(schema=shared_schema)
    try:
        session.sql(f"USE ROLE {role}").collect()
        session.sql(f"USE DATABASE {db}").collect()
        session.sql(f"USE WAREHOUSE {wh}").collect()
        session.sql(f"USE SCHEMA {db}.{shared_schema}").collect()

        logger.info("📋 Creating core PUDO tables in %s.%s...", db, shared_schema)
        execute_sql_file(session, sql_dir / "tables" / "pudo_tables.sql", database=db, schema=shared_schema)
        logger.info("✅ Tables created")
    finally:
        session.close()

    logger.info("📊 Generating and uploading PUDO datasets to SHARED_DATA...")
    try:
        subprocess.run(
            ["uv", "run", "pudo-generate", "generate"],
            check=True,
            capture_output=False,
        )
    except subprocess.CalledProcessError as e:
        logger.error("❌ Failed to generate and upload data: %s", e)
        sys.exit(1)

    logger.info("✅ %s.%s populated", db, shared_schema)
    logger.info("Tables: PUDO_REFERENCE, PARCELS, DELIVERY_ATTEMPTS, PUDO_OCCUPANCY")


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    sql_dir = script_dir / "sql"
    setup_shared_data(sql_dir)


if __name__ == "__main__":
    main()
