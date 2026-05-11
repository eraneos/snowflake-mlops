"""Inference-block helpers.

Duplicated from ``mock_data/src/pudo_data/inference_utils.py`` per ADR-0001
(no cross-component imports). The mock-data copy is authoritative; refactor
once ADR-0020 lands.
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
    """Earliest date with morning data but no predictions, or None if up to date."""
    try:
        morning_data_df = (
            session.table(f"{database}.{shared_data_schema}.DATA_GENERATION_LOG")
            .filter(col("PHASE") == "morning")
            .select("SIMULATION_DATE")
            .distinct()
        )

        predictions_df = (
            session.table(f"{database}.{predictions_schema}.PREDICTIONS")
            .select(col("PREDICTION_DATE").alias("SIMULATION_DATE"))
            .distinct()
        )

        pending_dates_df = (
            morning_data_df.join(
                predictions_df,
                on="SIMULATION_DATE",
                how="left_anti",
            )
            .sort(col("SIMULATION_DATE"))
            .limit(1)
        )

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
