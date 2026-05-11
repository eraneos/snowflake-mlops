"""Utilities for DAG operations and monitoring."""

import logging
import time

from snowflake.core.task.dagv1 import DAG
from snowflake.snowpark import Session

logger = logging.getLogger(__name__)


def wait_for_dag_run_to_complete(session: Session, dag: DAG, database_name: str, schema_name: str) -> str:
    """Wait for a DAG run to complete and return the final status.

    This function monitors the most recent DAG run and waits for it to complete.
    It uses exponential backoff to poll the task graph status and returns the final result.

    Args:
        session: Snowflake session object
        dag: The DAG object to monitor
        database_name: Database name where the DAG is deployed (from config, without quotes)
        schema_name: Schema name where the DAG is deployed (from config, without quotes)

    Returns:
        str: The final status of the DAG run (e.g., "SUCCEEDED", "FAILED")

    Raises:
        RuntimeError: If no recent runs are found for the DAG

    Note:
        Database and schema names should come from config object (e.g., config.database, config.schema_name)
        which provide unquoted values. Do not use session.get_current_database/schema() as they return
        quoted values (e.g., '"OSS_SF_MLOPS"') which won't match in WHERE clauses.
    """
    # NOTE: We assume the most recent run is our run
    # It would be better to add some unique identifier to the DAG to make it easier to identify the run
    recent_runs = session.sql(
        f"""
        SELECT run_id
        FROM table({database_name}.information_schema.current_task_graphs(
            root_task_name => '{dag.name.upper()}'
        ))
        WHERE database_name = '{database_name}'
          AND schema_name = '{schema_name}'
          AND scheduled_from = 'EXECUTE TASK'
        ORDER BY scheduled_time DESC
        LIMIT 1
        """
    ).collect()

    if len(recent_runs) == 0:
        msg = "No recent runs found. Did the DAG fail to run?"
        raise RuntimeError(msg)

    run_id = recent_runs[0][0]
    logger.info(f"DAG runId: {run_id}")

    start_time = time.time()
    dag_result = None

    while dag_result is None:
        result = session.sql(
            f"""
            SELECT state
            FROM table({database_name}.information_schema.complete_task_graphs(
                root_task_name => '{dag.name.upper()}'
            ))
            WHERE database_name = '{database_name}'
              AND schema_name = '{schema_name}'
              AND run_id = {run_id}
            """
        ).collect()

        if len(result) > 0:
            dag_result = result[0][0]
            elapsed = time.time() - start_time
            logger.info(f"DAG completed after {elapsed:.2f} seconds with result {dag_result}")
            break

        # Exponential backoff capped at 5 seconds
        wait_time = min(2 ** ((time.time() - start_time) / 10), 5)
        time.sleep(wait_time)

    return dag_result
