"""Incremental data generator for workshop inference pipeline.

This module provides functionality to generate daily batches of PUDO data
for simulating a rolling inference workflow. It supports two-phase generation:
1. Morning phase: Generate parcels and delivery attempts (without occupancy)
2. Evening phase: Generate ground truth occupancy data

This allows workshop participants to run inference on "unknown" data and later
evaluate predictions against actual outcomes.
"""

from datetime import date, datetime, timedelta
import logging

import pandas as pd
import polars as pl
from snowflake.snowpark import Session

from pudo_data.config_models import GenerationConfig
from pudo_data.core.config import infra_config
from pudo_data.core.environment import detect_environment, get_project_schema
from pudo_data.generators.delivery_attempts import DeliveryAttemptsGenerator
from pudo_data.generators.occupancy import OccupancyGenerator
from pudo_data.generators.parcels import ParcelsGenerator

logger = logging.getLogger(__name__)


class IncrementalDataGenerator:
    """Generator for incremental daily PUDO data batches.

    This generator creates daily data batches for inference simulation,
    allowing workshop participants to experience a realistic ML workflow
    where predictions must be made before actual outcomes are known.

    The generator maintains simulation state in the DATA_GENERATION_LOG
    table and automatically calculates the next simulation date.

    Attributes:
        session: Snowflake session for database operations
        config: Generation configuration parameters
        pudo_df: Reference PUDO DataFrame (loaded once)

    Example:
        >>> from pudo_data.core.session import create_session
        >>> from pudo_data.config_models import get_generation_config
        >>>
        >>> session = create_session()
        >>> config = get_generation_config()
        >>> generator = IncrementalDataGenerator(session, config)
        >>>
        >>> # Morning: Generate parcels and delivery attempts
        >>> generator.generate_morning_data()
        >>>
        >>> # Run inference (separate module)
        >>> # ...
        >>>
        >>> # Evening: Generate ground truth occupancy
        >>> generator.generate_evening_data()
    """

    def __init__(self, session: Session, config: GenerationConfig):
        """Initialize incremental data generator.

        Args:
            session: Active Snowflake session
            config: Generation configuration with parameters like parcels_per_day
        """
        self.session = session
        self.config = config
        self.pudo_df = None

        # Load infrastructure config for shared_data schema
        self.database = infra_config.database.name
        self.shared_data_schema = infra_config.shared_data.schema_name
        self.schema_name = get_project_schema(detect_environment())  # `PUDO_<ENV>` per ADR-0004

    def _load_pudo_reference(self) -> pl.DataFrame:
        """Load PUDO reference data from Snowflake shared data schema.

        Returns:
            Polars DataFrame with PUDO reference data
        """
        if self.pudo_df is None:
            logger.info(f"Loading PUDO reference data from {self.shared_data_schema}...")
            pudo_snowpark_df = self.session.table(f"{self.database}.{self.shared_data_schema}.PUDO_REFERENCE")
            self.pudo_df = pl.from_pandas(pudo_snowpark_df.to_pandas())
            logger.info(f"Loaded {len(self.pudo_df)} PUDOs")
        return self.pudo_df

    def get_next_simulation_date(self) -> date:
        """Calculate the next simulation date based on existing data in shared data schema.

        Queries existing PARCELS data to find the last date, as this represents
        the actual historical data. The DATA_GENERATION_LOG tracks incremental additions
        but should be consistent with PARCELS.

        Returns:
            date: The next simulation date to generate
        """
        # Check existing PARCELS data (primary source of truth)
        try:
            result = self.session.sql(
                f"""
                SELECT MAX(CREATED_DATE) as LAST_DATE
                FROM {self.database}.{self.shared_data_schema}.PARCELS
            """
            ).collect()

            if result and result[0]["LAST_DATE"]:
                last_date = result[0]["LAST_DATE"]
                next_date = last_date + timedelta(days=1)
                logger.info(
                    f"Last parcel date in {self.shared_data_schema}: {last_date}, next simulation date: {next_date}"
                )
                return next_date
        except Exception as e:
            logger.debug(f"Could not query parcels: {e}")

        # Fallback: Check generation log
        try:
            result = self.session.sql(
                f"""
                SELECT MAX(SIMULATION_DATE) as LAST_DATE
                FROM {self.database}.{self.shared_data_schema}.DATA_GENERATION_LOG
                WHERE PHASE = 'morning'
            """
            ).collect()

            if result and result[0]["LAST_DATE"]:
                last_date = result[0]["LAST_DATE"]
                next_date = last_date + timedelta(days=1)
                logger.info(f"Last simulation date from log: {last_date}, next: {next_date}")
                return next_date
        except Exception as e:
            logger.debug(f"Could not query generation log: {e}")

        # Default: Start from a sensible date
        default_date = date(2024, 1, 1)
        logger.info(f"No existing data found, starting from {default_date}")
        return default_date

    def get_simulation_status(self) -> dict:
        """Get current simulation status and statistics from shared data schema.

        Returns:
            dict: Status information including:
                - next_simulation_date: Next date to generate
                - total_days_generated: Total simulation days
                - last_morning_date: Last morning phase date
                - last_evening_date: Last evening phase date
                - pending_predictions: Dates needing predictions
        """
        status = {}

        # Get next simulation date
        status["next_simulation_date"] = self.get_next_simulation_date()

        # Get total days generated
        try:
            result = self.session.sql(
                f"""
                SELECT COUNT(DISTINCT SIMULATION_DATE) as TOTAL_DAYS
                FROM {self.database}.{self.shared_data_schema}.DATA_GENERATION_LOG
            """
            ).collect()
            status["total_days_generated"] = result[0]["TOTAL_DAYS"] if result else 0
        except Exception:
            status["total_days_generated"] = 0

        # Get last phase dates
        try:
            result = self.session.sql(
                f"""
                SELECT
                    MAX(CASE WHEN PHASE = 'morning' THEN SIMULATION_DATE END) as LAST_MORNING,
                    MAX(CASE WHEN PHASE = 'evening' THEN SIMULATION_DATE END) as LAST_EVENING
                FROM {self.database}.{self.shared_data_schema}.DATA_GENERATION_LOG
            """
            ).collect()
            if result:
                status["last_morning_date"] = result[0]["LAST_MORNING"]
                status["last_evening_date"] = result[0]["LAST_EVENING"]
        except Exception:
            status["last_morning_date"] = None
            status["last_evening_date"] = None

        # Get dates with morning data but no predictions
        try:
            # Get current schema from session
            current_schema_result = self.session.sql("SELECT CURRENT_SCHEMA()").collect()
            current_schema = current_schema_result[0][0] if current_schema_result else "UNKNOWN"

            result = self.session.sql(
                f"""
                SELECT DISTINCT l.SIMULATION_DATE
                FROM {self.database}.{self.shared_data_schema}.DATA_GENERATION_LOG l
                WHERE l.PHASE = 'morning'
                  AND NOT EXISTS (
                      SELECT 1 FROM {self.database}.{current_schema}.PREDICTIONS p
                      WHERE p.PREDICTION_DATE = l.SIMULATION_DATE
                  )
                ORDER BY l.SIMULATION_DATE
            """
            ).collect()
            status["pending_predictions"] = [row["SIMULATION_DATE"] for row in result]
        except Exception as e:
            # Log the error for debugging
            logger.warning(f"Could not determine pending predictions: {e}")
            status["pending_predictions"] = []

        return status

    def get_latest_pending_date(self) -> date | None:
        """Get the earliest date with morning data but no predictions.

        Delegates to the inference_utils module for a Snowpark-based approach
        that works in both local and Snowflake DAG environments.

        Returns:
            date: Earliest pending prediction date, or None if no pending dates exist

        Example:
            >>> generator = IncrementalDataGenerator(session, config)
            >>> pending_date = generator.get_latest_pending_date()
            >>> if pending_date:
            ...     print(f"Need to generate predictions for {pending_date}")
        """
        from pudo_data.inference_utils import get_latest_pending_date as _get_pending

        return _get_pending(
            session=self.session,
            database=self.database,
            shared_data_schema=self.shared_data_schema,
            predictions_schema=self.schema_name,
        )

    def generate_morning_data(self, target_date: date | None = None) -> dict:
        """Generate morning phase data: parcels and delivery attempts.

        This phase generates data that would be "known" in the morning:
        - New parcels created
        - Delivery attempts made
        - But NOT the final occupancy (that's evening phase)

        Args:
            target_date: Specific date to generate (default: next simulation date)

        Returns:
            dict: Generation statistics including:
                - simulation_date: Date generated
                - parcels_count: Number of parcels generated
                - attempts_count: Number of delivery attempts generated
        """
        if target_date is None:
            target_date = self.get_next_simulation_date()

        logger.info(f"Generating morning data for {target_date}")

        # Load PUDO reference
        pudo_df = self._load_pudo_reference()

        # Generate parcels for this date
        logger.info(f"Generating parcels for {target_date}...")
        parcels_gen = ParcelsGenerator(self.config)

        # Override config for single day
        original_days = self.config.n_days
        self.config.n_days = 1
        parcels_df = parcels_gen.generate()
        self.config.n_days = original_days

        # Set the target date (as Python date object for proper Pandas conversion)
        parcels_df = parcels_df.with_columns(pl.lit(target_date).alias("CREATED_DATE"))

        # Generate delivery attempts
        logger.info(f"Generating delivery attempts for {target_date}...")
        attempts_gen = DeliveryAttemptsGenerator(self.config, pudo_df, parcels_df)
        attempts_df = attempts_gen.generate()

        # Set the attempt date
        attempts_df = attempts_df.with_columns(pl.lit(target_date).alias("ATTEMPT_DATE"))

        # Upload to Snowflake (append mode)
        logger.info("Uploading to Snowflake...")
        self._append_to_snowflake({"PARCELS": parcels_df.to_pandas(), "DELIVERY_ATTEMPTS": attempts_df.to_pandas()})

        # Log generation
        self._log_generation(target_date, "morning", len(parcels_df) + len(attempts_df))

        stats = {"simulation_date": target_date, "parcels_count": len(parcels_df), "attempts_count": len(attempts_df)}

        logger.info(f"Morning data generated: {stats}")
        return stats

    def generate_evening_data(self, target_date: date | None = None) -> dict:
        """Generate evening phase data: ground truth occupancy.

        This phase generates the actual occupancy data that would be
        "known" at the end of the day. This provides ground truth for
        evaluating predictions made during the day.

        Args:
            target_date: Specific date to generate (default: last morning date)

        Returns:
            dict: Generation statistics including:
                - simulation_date: Date generated
                - occupancy_count: Number of occupancy records generated
                - predictions_updated: Number of predictions updated with actuals
        """
        if target_date is None:
            # Default to last morning date (generate evening for most recent day)
            status = self.get_simulation_status()
            if status["last_morning_date"] is None:
                msg = "No morning data found. Generate morning data first."
                raise ValueError(msg)
            target_date = status["last_morning_date"]

        logger.info(f"Generating evening data for {target_date}")

        # Load PUDO reference
        pudo_df = self._load_pudo_reference()

        # Load delivery attempts for this date
        logger.info(f"Loading delivery attempts for {target_date}...")
        attempts_snowpark_df = self.session.sql(
            f"""
            SELECT * FROM {self.database}.{self.shared_data_schema}.DELIVERY_ATTEMPTS
            WHERE ATTEMPT_DATE = '{target_date}'
        """
        )
        attempts_df = pl.from_pandas(attempts_snowpark_df.to_pandas())

        if len(attempts_df) == 0:
            msg = f"No delivery attempts found for {target_date}. Generate morning data first."
            raise ValueError(msg)

        # Generate occupancy
        logger.info(f"Generating occupancy for {target_date}...")
        occupancy_gen = OccupancyGenerator(self.config, pudo_df, attempts_df)
        occupancy_df = occupancy_gen.generate()

        # Upload to Snowflake (append mode)
        logger.info("Uploading occupancy to Snowflake...")
        self._append_to_snowflake({"PUDO_OCCUPANCY": occupancy_df.to_pandas()})

        # Update predictions with actual values
        predictions_updated = self._backfill_predictions(target_date, occupancy_df)

        # Log generation
        self._log_generation(target_date, "evening", len(occupancy_df))

        stats = {
            "simulation_date": target_date,
            "occupancy_count": len(occupancy_df),
            "predictions_updated": predictions_updated,
        }

        logger.info(f"Evening data generated: {stats}")
        return stats

    def _append_to_snowflake(self, datasets: dict[str, pd.DataFrame]) -> None:
        """Append datasets to existing Snowflake tables in shared data schema.

        Args:
            datasets: Dictionary mapping table names to pandas DataFrames
        """
        for table_name, df in datasets.items():
            logger.info(f"Appending {len(df)} rows to {self.shared_data_schema}.{table_name}...")
            snowpark_df = self.session.create_dataframe(df)

            # Get DataFrame column names for explicit INSERT
            columns = snowpark_df.columns
            columns_str = ", ".join(columns)

            # Use explicit column list to avoid CREATED_AT column mismatch
            # Create temp table, then INSERT with explicit columns
            temp_table = f"TEMP_{table_name}_{int(datetime.now().timestamp())}"
            snowpark_df.write.mode("overwrite").save_as_table(temp_table)

            # Insert into shared data table from temp table with explicit columns
            insert_sql = f"""
                INSERT INTO {self.database}.{self.shared_data_schema}.{table_name} ({columns_str})
                SELECT {columns_str} FROM {temp_table}
            """
            self.session.sql(insert_sql).collect()

            # Drop temp table
            self.session.sql(f"DROP TABLE IF EXISTS {temp_table}").collect()

    def _log_generation(self, simulation_date: date, phase: str, records_added: int) -> None:
        """Log data generation to DATA_GENERATION_LOG table in shared data schema.

        Args:
            simulation_date: Date that was generated
            phase: Generation phase ('morning' or 'evening')
            records_added: Total number of records added
        """
        # Insert directly with SQL to avoid column mismatch (LOG_ID is auto-increment, REAL_TIMESTAMP has default)
        try:
            log_table = f"{self.database}.{self.shared_data_schema}.DATA_GENERATION_LOG"
            insert_sql = f"""
                INSERT INTO {log_table} (SIMULATION_DATE, PHASE, RECORDS_ADDED, STATUS)
                VALUES ('{simulation_date}', '{phase}', {records_added}, 'SUCCESS')
            """
            self.session.sql(insert_sql).collect()
        except Exception as e:
            logger.warning(f"Could not log generation (may already exist): {e}")

    def _backfill_predictions(self, target_date: date, occupancy_df: pl.DataFrame) -> int:
        """Update PREDICTIONS table with actual fill rates.

        Args:
            target_date: Date to backfill
            occupancy_df: Occupancy DataFrame with actual fill rates

        Returns:
            int: Number of predictions updated
        """
        try:
            # Create a mapping of PUDO_ID -> FILL_RATE
            for row in occupancy_df.iter_rows(named=True):
                pudo_id = row["PUDO_ID"]
                fill_rate = row["FILL_RATE"]

                update_sql = f"""
                UPDATE {self.database}.{self.schema_name}.PREDICTIONS
                SET ACTUAL_FILL_RATE = {fill_rate},
                    PREDICTION_ERROR = PREDICTED_FILL_RATE - {fill_rate}
                WHERE PUDO_ID = {pudo_id}
                  AND PREDICTION_DATE = '{target_date}'
                  AND ACTUAL_FILL_RATE IS NULL
                """
                self.session.sql(update_sql).collect()

            # Count updated predictions
            result = self.session.sql(
                f"""
                SELECT COUNT(*) as UPDATED
                FROM {self.database}.{self.schema_name}.PREDICTIONS
                WHERE PREDICTION_DATE = '{target_date}'
                  AND ACTUAL_FILL_RATE IS NOT NULL
            """
            ).collect()

            return result[0]["UPDATED"] if result else 0
        except Exception as e:
            logger.warning(f"Could not backfill predictions: {e}")
            return 0
