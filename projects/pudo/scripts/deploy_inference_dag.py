#!/usr/bin/env python3
"""Deploy inference DAG for PUDO capacity prediction.

**DOMAIN SCRIPT** - Requires foundation infrastructure from deploy_schema.py

This script deploys the inference DAG that automatically generates predictions
for pending dates. Scheduling is controlled by config files only.

Prerequisites:
    Run deploy_schema.py first to create schema, stages, and tables.

Example usage:
    uv run python scripts/deploy_inference_dag.py
    uv run python scripts/deploy_inference_dag.py --run-dag
"""

import argparse
from datetime import datetime
import logging
import sys

from snowflake.core import Root

from pudo.core.config.infrastructure import config as infra_config
from pudo.core.environment import detect_environment, get_feature_store_schema, get_project_schema
from pudo.core.snowflake_session import create_session
from pudo.core.utils import wait_for_dag_run_to_complete
from pudo.inference.dag_definition import _ensure_environment, create_inference_dag

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def verify_infrastructure(session, database: str, schema: str, inference_config) -> bool:
    """Verify that schema, stage, and PREDICTIONS table exist.

    Args:
        session: Snowflake session
        database: Database name
        schema: Schema name
        inference_config: Inference config with stage names

    Returns:
        True if all infrastructure exists, False otherwise
    """
    try:
        # Check if schema exists
        # S608: SQL injection is not a risk - database and schema come from trusted config
        result = session.sql(
            f"""
            SELECT SCHEMA_NAME
            FROM {database}.INFORMATION_SCHEMA.SCHEMATA
            WHERE SCHEMA_NAME = '{schema}'
            """
        ).collect()

        if not result:
            logger.error("")
            logger.error(f"❌ Schema {schema} does not exist!")
            logger.error("")
            logger.error("Please run deploy_schema.py first to create the foundation infrastructure:")
            logger.error("   uv run python scripts/deploy_schema.py")
            logger.error("")
            return False

        # Check if INFERENCE_DAG_STAGE exists
        stage_name = inference_config.pipeline.dag_stage
        result = session.sql(f"SHOW STAGES LIKE '{stage_name}' IN SCHEMA {database}.{schema}").collect()

        if not result:
            logger.error("")
            logger.error(f"❌ Stage {stage_name} does not exist!")
            logger.error("")
            logger.error("Please run deploy_schema.py first to create the foundation infrastructure:")
            logger.error("   uv run python scripts/deploy_schema.py")
            logger.error("")
            return False

        # Check if PREDICTIONS table exists
        result = session.sql(f"SHOW TABLES LIKE 'PREDICTIONS' IN SCHEMA {database}.{schema}").collect()

        if not result:
            logger.error("")
            logger.error("❌ PREDICTIONS table does not exist!")
            logger.error("")
            logger.error("Please run deploy_schema.py first to create the foundation infrastructure:")
            logger.error("   uv run python scripts/deploy_schema.py")
            logger.error("")
            return False

        return True

    except Exception as e:
        logger.error(f"❌ Error verifying infrastructure: {e}")
        return False


def main():
    """Main deployment workflow."""
    parser = argparse.ArgumentParser(
        "Deploy Inference DAG",
        description="Deploy and optionally run the inference DAG.",
    )
    parser.add_argument(
        "--run-dag",
        action="store_true",
        default=False,
        help="Execute the DAG immediately after deployment.",
    )
    args = parser.parse_args()

    logger.info("🚀 Starting Inference DAG Deployment")
    logger.info("=" * 60)

    # Get configuration
    from pudo.core.config.ml.inference import config as inference_config

    environment = detect_environment()
    current_database = infra_config.database.name
    current_schema = get_project_schema(environment)
    current_warehouse = infra_config.warehouse.name
    feature_store = get_feature_store_schema(environment)
    shared_data_schema = infra_config.shared_data.schema_name

    # Use schedule from config only
    schedule = inference_config.inference.schedule

    session = create_session()
    session.append_query_tag("inference_dag_deploy")
    session.append_query_tag(datetime.utcnow().strftime("%Y%m%d_%H%M%S"))

    logger.info(f"Database: {current_database}")
    logger.info(f"Schema: {current_schema}")
    logger.info(f"Warehouse: {current_warehouse}")
    logger.info(f"Feature Store: {feature_store}")
    logger.info(f"Model: {inference_config.model.name}")
    logger.info("=" * 60)

    # Verify infrastructure exists
    logger.info("🔍 Verifying infrastructure...")
    if not verify_infrastructure(session, current_database, current_schema, inference_config):
        sys.exit(1)

    stage_name = inference_config.pipeline.dag_stage
    logger.info(f"✅ Schema {current_schema} exists")
    logger.info(f"✅ Stage {stage_name} exists")
    logger.info("✅ PREDICTIONS table exists")

    # Package and upload code
    dag_stage = f"@{current_database}.{current_schema}.{stage_name}"
    logger.info("📦 Packaging and uploading pudo module...")
    _ensure_environment(session=session, dag_stage=dag_stage)
    logger.info("✅ Module uploaded successfully")

    # Create and deploy DAG
    logger.info("📋 Creating inference DAG...")
    api_root = Root(session)
    db = api_root.databases[current_database]
    schema_obj = db.schemas[current_schema]

    from snowflake.core import CreateMode
    from snowflake.core.task.dagv1 import DAGOperation

    dag_op = DAGOperation(schema_obj)

    # Load feature view configs and prepare for DAG (avoid deepmerge import in UDF)
    import json

    from pudo.core.config.ml.feature_views import config as fv_config

    feature_view_configs = []
    for fv_name in ["pudo__historical_features", "pudo__geospatial_features", "pudo__temporal_features"]:
        fv_cfg = fv_config.feature_views[fv_name]
        if fv_cfg.enabled:
            feature_view_configs.append({"name": fv_name, "version": fv_cfg.version})
            logger.info(f"Including feature view: {fv_name} v{fv_cfg.version}")
        else:
            logger.info(f"Skipping disabled feature view: {fv_name}")

    dag_config = {
        "model_name": inference_config.model.name,
        "feature_store": feature_store,
        "shared_data_schema": shared_data_schema,
        "database": current_database,
        "schema_name": current_schema,
        "environment": environment,  # Resolved in-task via get_environment_from_context (ADR-0004)
        "alert_threshold": inference_config.inference.alert_threshold,
        "use_latest_promoted": inference_config.model.use_latest_promoted,
        "fallback_to_latest_version": inference_config.model.fallback_to_latest_version,
        "feature_view_configs": json.dumps(feature_view_configs),  # Serialize for DAG config
    }

    dag = create_inference_dag(
        name="inference_dag",
        warehouse=current_warehouse,
        stage_location=stage_name,
        dag_stage=dag_stage,
        schedule=schedule,
        **dag_config,
    )

    logger.info("🔄 Deploying DAG...")
    dag_op.deploy(dag, mode=CreateMode.or_replace)
    logger.info("✅ DAG deployed successfully!")

    if schedule:
        logger.info(f"📅 DAG scheduled with: {schedule}")
    else:
        logger.info("📅 DAG deployed without schedule (manual execution only)")

    logger.info("=" * 60)

    # Run DAG if requested
    if args.run_dag:
        logger.info("▶️  Running inference DAG...")
        dag_op.run(dag)

        result = wait_for_dag_run_to_complete(session, dag, current_database, current_schema)

        if result != "SUCCEEDED":
            logger.error(f"❌ DAG failed with result: {result}")
            msg = f"Inference DAG failed with result {result}"
            raise RuntimeError(msg)

        logger.info("✅ Inference DAG execution completed successfully!")
    else:
        logger.info("💡 To run the DAG manually, use:")
        dag_task_name = inference_config.pipeline.dag_name
        logger.info(f"   EXECUTE TASK {current_database}.{current_schema}.{dag_task_name};")

    logger.info("=" * 60)
    logger.info("🎉 Inference DAG deployment complete!")

    session.close()


if __name__ == "__main__":
    main()
