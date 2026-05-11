#!/usr/bin/env python3
"""Deploy ML training DAG for the current environment.

**DOMAIN SCRIPT** - Requires foundation infrastructure from deploy_schema.py

This script:
1. Verifies the project schema and stages exist (created by deploy_schema.py)
2. Deploys the ML training DAG with environment-specific configuration

Usage:
    uv run python scripts/deploy_training_dag.py
    uv run python scripts/deploy_training_dag.py --run-dag

Prerequisites:
    Run deploy_schema.py first to create the project schema and stages.

Environment detection (per ADR-0004): feat/*, bugfix/* → dev; main → staging; v* tags → prod.
"""

import argparse
from datetime import datetime
import logging
from pathlib import Path
import sys

from snowflake.core import CreateMode, Root
from snowflake.core.task.dagv1 import DAGOperation

from pudo.core.config.infrastructure import config as infra_config
from pudo.core.config.ml.feature_views import config as feature_views_config
from pudo.core.config.ml.training import config as training_config
from pudo.core.environment import detect_environment, get_feature_store_schema, get_project_schema
from pudo.core.snowflake_session import create_session
from pudo.core.utils import wait_for_dag_run_to_complete
from pudo.training.dag_definition import _ensure_environment, create_dag

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def verify_infrastructure(session, database: str, schema: str, training_pipeline_config) -> bool:
    """Verify that schema and required stages exist.

    Args:
        session: Snowflake session
        database: Database name
        schema: Schema name
        training_pipeline_config: Training pipeline config with stage names

    Returns:
        True if all infrastructure exists, False otherwise
    """
    try:
        # Check if schema exists
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

        # Check if required stages exist
        stages = [training_pipeline_config.dag_stage, training_pipeline_config.job_stage]
        for stage_name in stages:
            result = session.sql(f"SHOW STAGES LIKE '{stage_name}' IN SCHEMA {database}.{schema}").collect()

            if not result:
                logger.error("")
                logger.error(f"❌ Stage {stage_name} does not exist!")
                logger.error("")
                logger.error("Please run deploy_schema.py first to create the foundation infrastructure:")
                logger.error("   uv run python scripts/deploy_schema.py")
                logger.error("")
                return False

        return True

    except Exception as e:
        logger.error(f"❌ Error verifying infrastructure: {e}")
        return False


def deploy_dag(
    *,
    run_dag: bool = False,
):
    """Deploy DAG for current environment.

    Args:
        run_dag: Execute DAG immediately after deployment
    """
    # Load configuration
    database = infra_config.database.name
    environment = detect_environment()
    schema = get_project_schema(environment)
    warehouse = infra_config.warehouse.name
    role = infra_config.role.name
    feature_store = get_feature_store_schema(environment)
    shared_data_schema = infra_config.shared_data.schema_name

    # Select compute pool based on environment
    compute_pool = infra_config.compute_pools.dev.name if environment == "dev" else infra_config.compute_pools.prod.name

    logger.info("🚀 Deploying ML Training DAG")
    logger.info("=" * 50)
    logger.info("")
    logger.info("📋 Configuration:")
    logger.info(f"  Database:         {database}")
    logger.info(f"  Schema:           {schema}")
    logger.info(f"  Environment:      {environment}")
    logger.info(f"  Compute Pool:     {compute_pool}")
    logger.info(f"  Feature Store:    {feature_store}")
    logger.info(f"  DAG Name:         {training_config.pipeline.dag_name}")
    logger.info(f"  Model Name:       {training_config.model.name}")
    logger.info(f"  Dataset Name:     {training_config.dataset.name}")
    logger.info("")
    logger.info("⚙️  Training Configuration:")
    schedule_display = (
        training_config.execution.schedule if training_config.execution.schedule else "Manual execution only"
    )
    logger.info(f"  Schedule:         {schedule_display}")
    logger.info(f"  Use GPU:          {training_config.execution.use_gpu}")
    logger.info(f"  Target Instances: {training_config.execution.target_instances}")
    metric_info = (
        f"  Metric:           {training_config.evaluation.metric_name} "
        f"(threshold: {training_config.evaluation.metric_threshold})"
    )
    logger.info(metric_info)
    logger.info(f"  Training Data:    {training_config.dataset.train_days} days")
    logger.info(f"  Validation Data:  {training_config.dataset.val_days} days")
    logger.info(f"  Test Data:        {training_config.dataset.test_days} days")
    logger.info("")
    logger.info("🎬 Execution:")
    logger.info(f"  Run DAG:          {run_dag}")
    logger.info("")

    # Create session
    logger.info("🔐 Connecting to Snowflake...")
    session = create_session()

    try:
        # Set context
        session.sql(f"USE ROLE {role}").collect()
        session.sql(f"USE DATABASE {database}").collect()
        session.sql(f"USE WAREHOUSE {warehouse}").collect()
        session.sql(f"USE SCHEMA {schema}").collect()

        # Verify infrastructure exists
        logger.info("")
        logger.info("🔍 Verifying infrastructure...")
        if not verify_infrastructure(session, database, schema, training_config.pipeline):
            sys.exit(1)

        logger.info(f"✅ Schema {schema} exists")
        logger.info(f"✅ Stage {training_config.pipeline.dag_stage} exists")
        logger.info(f"✅ Stage {training_config.pipeline.job_stage} exists")

        # Get API root for DAG operations
        api_root = Root(session)
        db = api_root.databases[database]
        schema_obj = db.schemas[schema]

        # Prepare stage paths from training config
        dag_stage = f"@{database}.{schema}.{training_config.pipeline.dag_stage}"
        job_stage = f"@{database}.{schema}.{training_config.pipeline.job_stage}"
        data_table = f"{database}.{shared_data_schema}.{training_config.dataset.source_table}"

        # Ensure environment (package modules, etc.)
        logger.info("")
        logger.info("📦 Preparing environment...")
        _ensure_environment(session=session, dag_stage=dag_stage, job_stage=job_stage)
        logger.info("✅ Environment prepared")

        # Create DAG
        logger.info("")
        logger.info("🚀 Creating DAG...")
        logger.info(f"  Name: {training_config.pipeline.dag_name}")

        # Load FV versions from ML config (local load, passed to remote DAG tasks)
        feature_views = []
        for fv_cfg in feature_views_config.feature_views.values():
            if fv_cfg.enabled:
                feature_views.append({"name": fv_cfg.snowflake_name, "version": fv_cfg.version})
                logger.info(f"  Feature View: {fv_cfg.snowflake_name} v{fv_cfg.version}")

        if not feature_views:
            logger.error("❌ No enabled feature views found in config!")
            sys.exit(1)

        # Serialize feature_views to JSON string (DAG config only accepts primitives)
        import json

        feature_views_json = json.dumps(feature_views)

        dag = create_dag(
            name=training_config.pipeline.dag_name,
            schedule=training_config.execution.schedule,
            warehouse=warehouse,
            stage_location=training_config.pipeline.dag_stage,
            dag_stage=dag_stage,
            job_stage=job_stage,
            data_table=data_table,
            use_gpu=training_config.execution.use_gpu,
            target_instances=training_config.execution.target_instances,
            compute_pool=compute_pool,
            dataset_name=training_config.dataset.name,
            feature_store=feature_store,
            feature_views=feature_views_json,  # Pass as JSON string (DAG config limitation)
            model_name=training_config.model.name,
            metric_name=training_config.evaluation.metric_name,
            metric_threshold=training_config.evaluation.metric_threshold,
            train_days=training_config.dataset.train_days,
            val_days=training_config.dataset.val_days,
            test_days=training_config.dataset.test_days,
            environment=environment,  # Resolved in-task via get_environment_from_context (ADR-0004)
        )

        # Deploy DAG
        logger.info("📤 Deploying DAG to Snowflake...")
        session.append_query_tag("dag_deployment")
        session.append_query_tag(datetime.utcnow().strftime("%Y%m%d_%H%M%S"))

        dag_op = DAGOperation(schema_obj)
        dag_op.deploy(dag, mode=CreateMode.or_replace)

        logger.info("✅ DAG deployed successfully")

        # Run DAG if requested
        if run_dag:
            logger.info("")
            logger.info("▶️  Starting DAG execution...")
            dag_op.run(dag)

            logger.info("⏳ Waiting for DAG to complete...")
            result = wait_for_dag_run_to_complete(session, dag, database, schema)

            if result == "SUCCEEDED":
                logger.info("✅ DAG execution completed successfully!")
            else:
                logger.error(f"❌ DAG execution failed with result: {result}")
                sys.exit(1)

        # Final summary
        logger.info("")
        logger.info("✅ Deployment complete!")
        logger.info("=" * 50)
        logger.info("")
        logger.info("📦 Deployed resources:")
        logger.info(f"   Database:      {database}")
        logger.info(f"   Schema:        {schema}")
        logger.info(f"   DAG:           {training_config.pipeline.dag_name}")
        logger.info(f"   Model:         {training_config.model.name}")
        logger.info(f"   Dataset:       {training_config.dataset.name}")
        logger.info(f"   Compute Pool:  {compute_pool}")
        logger.info("")

        if not run_dag:
            logger.info("💡 To run the DAG manually:")
            logger.info(f"   1. Go to Snowflake UI → Data → Databases → {database} → {schema}")
            logger.info(f"   2. Find the {training_config.pipeline.dag_name} task and execute it")
            logger.info("   OR run: uv run python scripts/deploy_training_dag.py --run-dag")
            logger.info("")

        logger.info("🔧 To redeploy just the DAG (skip feature store):")
        logger.info("   uv run python scripts/deploy_training_dag.py")

    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(
        description="Deploy and optionally run the ML training DAG for the current environment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--run-dag",
        action="store_true",
        default=False,
        help="Execute the DAG immediately after deployment",
    )
    args = parser.parse_args()

    # Check if .env exists
    if not Path(".env").exists():
        logger.error("❌ Error: .env file not found. Please create it from .env.example")
        sys.exit(1)

    # Deploy DAG
    try:
        deploy_dag(
            run_dag=args.run_dag,
        )
    except Exception as e:
        logger.error(f"❌ Deployment failed: {e}")
        logger.exception("Full traceback:")
        sys.exit(1)


if __name__ == "__main__":
    main()
