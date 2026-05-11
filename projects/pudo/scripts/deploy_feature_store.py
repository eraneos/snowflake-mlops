#!/usr/bin/env python3
"""Deploy feature store for the current environment.

**DOMAIN SCRIPT** - Requires foundation infrastructure from deploy_schema.py

This script:
1. Verifies that the project schema exists (created by deploy_schema.py)
2. Registers the PUDO entity and PUDO__ feature views in `FEATURE_STORE_<ENV>` (per ADR-0004)

Usage:
    uv run python scripts/deploy_feature_store.py

Prerequisites:
    Run deploy_schema.py first to create the project schema and stages.

Environment detection (per ADR-0004): feat/*, bugfix/* → dev; main → staging; v* tags → prod.
"""

import logging
from pathlib import Path
import sys

from pudo.core.config.infrastructure import config as infra_config
from pudo.core.environment import detect_environment, get_feature_store_schema, get_project_schema
from pudo.core.snowflake_session import create_session
from pudo.feature_view.feature_store import PUDOFeatureStore

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def verify_schema_exists(session, database_name: str, schema_name: str) -> bool:
    """Verify that schema exists.

    Args:
        session: Snowflake session
        database_name: Database name
        schema_name: Schema name

    Returns:
        True if schema exists, False otherwise
    """
    result = session.sql(f"SHOW SCHEMAS LIKE '{schema_name}' IN DATABASE {database_name}").collect()
    return len(result) > 0


def deploy_feature_store():
    """Deploy feature store for current environment.

    Uses unified config system which auto-detects environment from git branch
    and loads configs from config/feature_store/, config/ml/, and config/infrastructure.yaml.
    """
    # Detect environment from git branch
    environment = detect_environment()
    schema_name = get_project_schema(environment)
    feature_store_schema = get_feature_store_schema(environment)

    logger.info("🚀 Deploying Feature Store")
    logger.info("=" * 50)
    logger.info("")
    logger.info("📋 Configuration:")
    logger.info(f"  Database:         {infra_config.database.name}")
    logger.info(f"  Project Schema:   {schema_name}")
    logger.info(f"  Environment:      {environment}")
    logger.info(f"  Feature Store:    {feature_store_schema}")
    logger.info(f"  Warehouse:        {infra_config.warehouse.name}")
    logger.info(f"  Role:             {infra_config.role.name}")
    logger.info("")

    # Create session
    logger.info("🔐 Connecting to Snowflake...")
    session = create_session()

    try:
        # Set context
        session.sql(f"USE ROLE {infra_config.role.name}").collect()
        session.sql(f"USE DATABASE {infra_config.database.name}").collect()
        session.sql(f"USE WAREHOUSE {infra_config.warehouse.name}").collect()

        # Step 1: Verify schema exists
        logger.info("")
        logger.info("🔍 Step 1: Verifying infrastructure...")
        logger.info("=" * 50)

        if not verify_schema_exists(session, infra_config.database.name, schema_name):
            logger.error("")
            logger.error(f"❌ Schema {schema_name} does not exist!")
            logger.error("")
            logger.error("Please run deploy_schema.py first to create the foundation infrastructure:")
            logger.error("  uv run python scripts/deploy_schema.py")
            logger.error("")
            sys.exit(1)

        logger.info(f"✅ Schema {schema_name} exists")

        # Step 2: Register feature store
        logger.info("")
        logger.info("📊 Step 2: Registering Feature Store...")
        logger.info("=" * 50)

        # Create PUDOFeatureStore instance (uses new hierarchical config system)
        pudo_fs = PUDOFeatureStore()

        # Override session with our existing session (already configured)
        pudo_fs.session = session

        # Register feature store
        logger.info(f"Registering entities and feature views in {schema_name}...")
        pudo_fs.setup_complete_feature_store()

        logger.info("")
        logger.info("✅ Feature store deployment complete!")
        logger.info("=" * 50)
        logger.info("")
        logger.info("📦 Deployed resources:")
        logger.info(f"   Database:       {infra_config.database.name}")
        logger.info(f"   Project Schema: {schema_name}")
        logger.info(f"   Feature Store:  {feature_store_schema}")
        logger.info(f"   Environment:    {environment}")
        logger.info("")
        logger.info("🎯 Next step:")
        logger.info("   Deploy training DAG: uv run python scripts/deploy_training_dag.py --run-dag")

    finally:
        session.close()


def main():
    # Check if .env exists
    if not Path(".env").exists():
        logger.error("❌ Error: .env file not found. Please create it from .env.example")
        sys.exit(1)

    # Deploy feature store
    try:
        deploy_feature_store()
    except Exception as e:
        logger.error(f"❌ Deployment failed: {e}")
        logger.exception("Full traceback:")
        sys.exit(1)


if __name__ == "__main__":
    main()
