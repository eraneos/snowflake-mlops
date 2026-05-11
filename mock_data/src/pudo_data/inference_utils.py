"""Utility functions for inference pipeline.

These functions use only Snowpark DataFrames and can run in both local
and Snowflake DAG environments (no Polars dependency).
"""

from datetime import date
import logging

from snowflake.snowpark import Session
from snowflake.snowpark.functions import col

logger = logging.getLogger(__name__)


def get_latest_pending_date(
    session: Session,
    database: str,
    shared_data_schema: str,
    predictions_schema: str,
) -> date | None:
    """Get the earliest date with morning data but no predictions.

    This function uses Snowpark DataFrames to check the DATA_GENERATION_LOG for dates
    with 'morning' phase that don't have corresponding entries in the PREDICTIONS table.
    Pure Snowpark approach works in both local and Snowflake DAG environments.

    Args:
        session: Snowflake session
        database: Database name
        shared_data_schema: Schema containing DATA_GENERATION_LOG
        predictions_schema: Schema containing PREDICTIONS table

    Returns:
        date: Earliest pending prediction date, or None if no pending dates exist

    Example:
        >>> from pudo_data.core.config import infra_config
        >>> from pudo_data.core.environment import detect_environment, get_project_schema
        >>> from pudo_data.core.session import create_session
        >>> session = create_session()
        >>> pending_date = get_latest_pending_date(
        ...     session=session,
        ...     database=infra_config.database.name,
        ...     shared_data_schema=infra_config.shared_data.schema_name,
        ...     predictions_schema=get_project_schema(detect_environment()),
        ... )
        >>> if pending_date:
        ...     print(f"Need to generate predictions for {pending_date}")
    """
    try:
        # Get dates with morning data from DATA_GENERATION_LOG
        morning_data_df = (
            session.table(f"{database}.{shared_data_schema}.DATA_GENERATION_LOG")
            .filter(col("PHASE") == "morning")
            .select("SIMULATION_DATE")
            .distinct()
        )

        # Get dates that already have predictions
        predictions_df = (
            session.table(f"{database}.{predictions_schema}.PREDICTIONS")
            .select(col("PREDICTION_DATE").alias("SIMULATION_DATE"))
            .distinct()
        )

        # Find dates with morning data but no predictions (left anti join)
        pending_dates_df = (
            morning_data_df.join(
                predictions_df,
                on="SIMULATION_DATE",
                how="left_anti",  # Only dates NOT in predictions
            )
            .sort(col("SIMULATION_DATE"))
            .limit(1)
        )

        # Collect the result
        pending_rows = pending_dates_df.collect()

        if len(pending_rows) == 0:
            logger.info("No pending predictions found")
            return None

        pending_date = pending_rows[0]["SIMULATION_DATE"]
        logger.info(f"Found pending prediction date: {pending_date}")
        return pending_date

    except Exception as e:
        logger.warning(f"Could not determine pending predictions: {e}")
        return None
