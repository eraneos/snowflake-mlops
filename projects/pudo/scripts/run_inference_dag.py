#!/usr/bin/env python3
"""Execute the inference DAG without redeploying.

This script runs an already-deployed inference DAG by executing the root task.
Use this for running inference cycles without redeploying the DAG definition.

Example usage:
    uv run python scripts/run_inference_dag.py
    uv run python scripts/run_inference_dag.py --no-wait
"""

import argparse
from datetime import datetime
import logging

from pudo.core.config.infrastructure import config as infra_config
from pudo.core.environment import detect_environment, get_project_schema
from pudo.core.snowflake_session import get_session
from pudo.core.utils import wait_for_dag_run_to_complete

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Execute the inference DAG."""
    parser = argparse.ArgumentParser(
        "Run Inference DAG",
        description="Execute the already-deployed inference DAG.",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        default=False,
        help="Don't wait for completion (fire and forget)",
    )
    args = parser.parse_args()

    logger.info("🚀 Executing Inference DAG")
    logger.info("=" * 60)

    # Get configuration
    from pudo.core.config.ml.inference import config as inference_config

    session = get_session()
    session.append_query_tag("inference_dag_execute")
    session.append_query_tag(datetime.utcnow().strftime("%Y%m%d_%H%M%S"))

    current_database = infra_config.database.name
    current_schema = get_project_schema(detect_environment())
    dag_name = inference_config.pipeline.dag_name

    logger.info(f"Database: {current_database}")
    logger.info(f"Schema: {current_schema}")
    logger.info(f"DAG Name: {dag_name.upper()}")
    logger.info("=" * 60)

    # Execute DAG
    logger.info(f"▶️  Executing {dag_name.upper()}...")

    try:
        # Execute via SQL
        execute_sql = f"EXECUTE TASK {current_database}.{current_schema}.{dag_name.upper()}"
        session.sql(execute_sql).collect()
        logger.info(f"✅ {dag_name.upper()} execution started")

        # Wait for completion unless fire-and-forget mode
        if not args.no_wait:
            logger.info("⏳ Waiting for DAG to complete...")

            # Create DAG object for monitoring (we need this for wait_for_dag_run_to_complete)
            from snowflake.core.task.dagv1 import DAG

            # Create a minimal DAG object just for monitoring (we only need the name)
            dag = DAG(dag_name)

            # Use the same monitoring logic as training DAG
            result = wait_for_dag_run_to_complete(session, dag, current_database, current_schema)

            if result == "SUCCEEDED":
                logger.info("✅ DAG completed successfully!")
            else:
                logger.error(f"❌ DAG failed with result: {result}")
                msg = f"Inference DAG failed with result {result}"
                raise RuntimeError(msg)
        else:
            logger.info("🔥 Fire-and-forget mode - not waiting for completion")

    except Exception as e:
        logger.error(f"❌ Failed to execute DAG: {e}")
        raise

    logger.info("=" * 60)
    logger.info("🎉 Inference DAG execution complete!")

    session.close()


if __name__ == "__main__":
    main()
