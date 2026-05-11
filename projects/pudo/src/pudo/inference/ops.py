"""Inference operations module for PUDO capacity prediction.

This module provides standalone functions for running inference pipelines,
evaluating predictions, and querying alerts. These operations can be called
from CLI commands, scripts, or tests.
"""

from datetime import date
import logging

import polars as pl
from snowflake.snowpark import Session
from snowflake.snowpark.functions import (
    abs as sf_abs,
    avg as sf_avg,
    col,
    count as sf_count,
    lit,
    sqrt,
    sum as sf_sum,
)

from pudo.core.config.infrastructure import config as infra_config
from pudo.core.config.ml.inference import config as inference_config
from pudo.core.environment import detect_environment, get_project_schema
from pudo.core.utils import wait_for_dag_run_to_complete

logger = logging.getLogger(__name__)


def run_inference(session: Session, target_date: date | None = None) -> dict:
    """Run the deployed inference DAG and return prediction statistics.

    This function triggers remote execution of the inference DAG in Snowflake,
    waits for completion, and returns statistics about the predictions generated.

    Args:
        session: Snowflake session object
        target_date: Optional specific date to predict (default: auto-detect from morning data)

    Returns:
        dict: Prediction statistics with keys:
            - prediction_date: Date predictions were generated for
            - model_version: Model version used
            - pudos_predicted: Total number of PUDOs predicted
            - high_risk_count: Number of PUDOs with predicted fill rate > 85%

    Raises:
        RuntimeError: If DAG execution fails or no predictions found

    Example:
        >>> from pudo.core.snowflake_session import create_session
        >>> session = create_session()
        >>> stats = run_inference(session)
        >>> print(f"Predicted {stats['pudos_predicted']} PUDOs")
    """
    schema_name = get_project_schema(detect_environment())
    database = infra_config.database.name

    logger.info(f"Starting inference DAG execution in {database}.{schema_name}")

    try:
        # Set context
        session.sql(f"USE ROLE {infra_config.role.name}").collect()
        session.sql(f"USE DATABASE {database}").collect()
        session.sql(f"USE SCHEMA {schema_name}").collect()

        # Get the DAG name from configuration
        dag_name = inference_config.pipeline.dag_name

        # Execute the deployed DAG
        logger.info(f"Executing DAG: {dag_name}")
        execute_sql = f"EXECUTE TASK {database}.{schema_name}.{dag_name}"
        session.sql(execute_sql).collect()

        # Wait for DAG completion
        logger.info("Waiting for DAG to complete...")

        # Create a minimal DAG object for wait_for_dag_run_to_complete
        # We only need the name attribute
        class DagRef:
            def __init__(self, name):
                self.name = name

        dag_ref = DagRef(dag_name)

        result = wait_for_dag_run_to_complete(
            session=session,
            dag=dag_ref,
            database_name=database,
            schema_name=schema_name,
        )

        if result != "SUCCEEDED":
            msg = f"Inference DAG failed with result: {result}"
            raise RuntimeError(msg)

        logger.info("✅ Inference DAG completed successfully")

        # Query predictions from the most recent run
        # S608: SQL injection is not a risk here - database and schema_name come from trusted config
        predictions_query = f"""
        SELECT
            PREDICTION_DATE,
            MODEL_VERSION,
            COUNT(*) as PUDOS_PREDICTED,
            SUM(CASE WHEN PREDICTED_FILL_RATE > 0.85 THEN 1 ELSE 0 END) as HIGH_RISK_COUNT
        FROM {database}.{schema_name}.PREDICTIONS
        WHERE PREDICTION_DATE = (
            SELECT MAX(PREDICTION_DATE)
            FROM {database}.{schema_name}.PREDICTIONS
        )
        GROUP BY PREDICTION_DATE, MODEL_VERSION
        """

        result_df = session.sql(predictions_query).collect()

        if not result_df:
            msg = "No predictions found after DAG execution"
            raise RuntimeError(msg)

        row = result_df[0]

        stats = {
            "prediction_date": str(row["PREDICTION_DATE"]),
            "model_version": row["MODEL_VERSION"],
            "pudos_predicted": int(row["PUDOS_PREDICTED"]),
            "high_risk_count": int(row["HIGH_RISK_COUNT"]),
        }

        logger.info(f"Inference complete: {stats}")
        return stats

    except Exception as e:
        logger.error(f"Failed to run inference: {e}")
        raise


def evaluate_predictions(session: Session, target_date: date | None = None) -> dict:
    """Evaluate prediction accuracy against actual outcomes.

    This function runs locally using Snowpark queries to compare predictions
    with actual PUDO occupancy data and calculate evaluation metrics.

    Args:
        session: Snowflake session object
        target_date: Optional specific date to evaluate (default: latest with actuals)

    Returns:
        dict: Evaluation metrics with keys:
            - prediction_date: Date evaluated
            - predictions_evaluated: Number of predictions with actual data
            - mae: Mean Absolute Error
            - rmse: Root Mean Squared Error
            - mean_error: Mean Error (bias)
            - total_alerts: Number of high-risk predictions (>85%)
            - correct_alerts: Number of correct high-risk predictions

    Raises:
        ValueError: If no predictions or actuals found for the date

    Example:
        >>> from pudo.core.snowflake_session import create_session
        >>> session = create_session()
        >>> metrics = evaluate_predictions(session)
        >>> print(f"MAE: {metrics['mae']:.4f}")
    """
    schema_name = get_project_schema(detect_environment())
    database = infra_config.database.name

    logger.info(f"Evaluating predictions in {database}.{schema_name}")

    try:
        # Determine target date
        if target_date is None:
            # Find latest date with predictions that also has actual occupancy data
            # S608: SQL injection is not a risk - database and schema_name from trusted config
            date_query = f"""
            SELECT DISTINCT p.PREDICTION_DATE
            FROM {database}.{schema_name}.PREDICTIONS p
            INNER JOIN {database}.SHARED_DATA.PUDO_OCCUPANCY o
                ON p.PUDO_ID = o.PUDO_ID
                AND p.PREDICTION_DATE = o.DATE
            ORDER BY p.PREDICTION_DATE DESC
            LIMIT 1
            """
            result = session.sql(date_query).collect()

            if not result:
                msg = "No predictions with actual data found"
                raise ValueError(msg)

            target_date = result[0]["PREDICTION_DATE"]
            logger.info(f"Auto-detected evaluation date: {target_date}")
        else:
            logger.info(f"Evaluating predictions for date: {target_date}")

        # Join predictions with actuals using SQL for clearer semantics
        # Note: PUDO_OCCUPANCY table has FILL_RATE column directly
        # S608: SQL injection not a risk - database/schema_name from config, target_date validated
        eval_sql = f"""
        SELECT
            p.PREDICTION_ID,
            p.PUDO_ID,
            p.PREDICTED_FILL_RATE,
            o.FILL_RATE AS ACTUAL_FILL_RATE
        FROM {database}.{schema_name}.PREDICTIONS p
        INNER JOIN {database}.SHARED_DATA.PUDO_OCCUPANCY o
            ON p.PUDO_ID = o.PUDO_ID
            AND p.PREDICTION_DATE = o.DATE
        WHERE p.PREDICTION_DATE = '{target_date}'
        """

        eval_df = session.sql(eval_sql)

        # Calculate error metrics
        eval_with_errors = eval_df.with_column("PREDICTION_ERROR", col("PREDICTED_FILL_RATE") - col("ACTUAL_FILL_RATE"))

        # Get evaluation statistics
        metrics_df = eval_with_errors.agg(
            [
                sf_count("*").alias("PREDICTIONS_EVALUATED"),
                sf_avg(sf_abs(col("PREDICTION_ERROR"))).alias("MAE"),
                sqrt(sf_avg(col("PREDICTION_ERROR") * col("PREDICTION_ERROR"))).alias("RMSE"),
                sf_avg("PREDICTION_ERROR").alias("MEAN_ERROR"),
                sf_sum((col("PREDICTED_FILL_RATE") > 0.85).cast("int")).alias("TOTAL_ALERTS"),
                sf_sum(((col("PREDICTED_FILL_RATE") > 0.85) & (col("ACTUAL_FILL_RATE") > 0.85)).cast("int")).alias(
                    "CORRECT_ALERTS"
                ),
            ]
        )

        metrics_row = metrics_df.collect()[0]

        if metrics_row["PREDICTIONS_EVALUATED"] == 0:
            msg = f"No predictions found for date {target_date}"
            raise ValueError(msg)

        # Update PREDICTIONS table with actual values and errors
        logger.info("Updating PREDICTIONS table with actual values...")

        # Create a temporary table with evaluation results
        eval_with_errors.create_or_replace_temp_view("TEMP_EVAL_RESULTS")

        # Use SQL UPDATE with a subquery (simpler and avoids merge duplicates)
        # S608: SQL injection not a risk - database and schema_name from trusted config
        update_sql = f"""
        UPDATE {database}.{schema_name}.PREDICTIONS p
        SET
            p.ACTUAL_FILL_RATE = e.ACTUAL_FILL_RATE,
            p.PREDICTION_ERROR = e.PREDICTION_ERROR
        FROM TEMP_EVAL_RESULTS e
        WHERE p.PREDICTION_ID = e.PREDICTION_ID
        """

        session.sql(update_sql).collect()
        logger.info(f"✅ Updated {metrics_row['PREDICTIONS_EVALUATED']} predictions with actual values")

        evaluation = {
            "prediction_date": str(target_date),
            "predictions_evaluated": int(metrics_row["PREDICTIONS_EVALUATED"]),
            "mae": float(metrics_row["MAE"]),
            "rmse": float(metrics_row["RMSE"]),
            "mean_error": float(metrics_row["MEAN_ERROR"]),
            "total_alerts": int(metrics_row["TOTAL_ALERTS"]),
            "correct_alerts": int(metrics_row["CORRECT_ALERTS"]),
        }

        logger.info(f"Evaluation complete: MAE={evaluation['mae']:.4f}, RMSE={evaluation['rmse']:.4f}")
        return evaluation

    except Exception as e:
        logger.error(f"Failed to evaluate predictions: {e}")
        raise


def get_current_alerts(session: Session) -> pl.DataFrame:
    """Get current high-risk PUDO alerts (predicted fill rate > 85%).

    This function runs locally using Snowpark queries to find PUDOs
    with high predicted capacity utilization.

    Args:
        session: Snowflake session object

    Returns:
        pl.DataFrame: Polars DataFrame with columns:
            - PUDO_ID: PUDO identifier
            - PUDO_NAME: PUDO name
            - PUDO_TYPE: Type (Shop, Locker, Post Office)
            - PREDICTION_DATE: Date of prediction
            - PREDICTED_FILL_RATE: Predicted fill rate (0-1)
            - CAPACITY: PUDO capacity
            - PREDICTED_OCCUPANCY: Estimated occupancy count

    Example:
        >>> from pudo.core.snowflake_session import create_session
        >>> session = create_session()
        >>> alerts = get_current_alerts(session)
        >>> print(f"Found {len(alerts)} high-risk PUDOs")
    """
    schema_name = get_project_schema(detect_environment())
    database = infra_config.database.name

    logger.info(f"Querying high-risk alerts from {database}.{schema_name}")

    try:
        # Query predictions and join with PUDO metadata
        predictions_df = session.table(f"{database}.{schema_name}.PREDICTIONS")
        pudo_ref_df = session.table(f"{database}.SHARED_DATA.PUDO_REFERENCE")

        # Get latest prediction date with high-risk alerts
        # S608: SQL injection not a risk - database and schema_name from trusted config
        latest_date_query = f"""
        SELECT MAX(PREDICTION_DATE) as LATEST_DATE
        FROM {database}.{schema_name}.PREDICTIONS
        WHERE PREDICTED_FILL_RATE > 0.85
        """

        date_result = session.sql(latest_date_query).collect()

        if not date_result or date_result[0]["LATEST_DATE"] is None:
            logger.info("No high-risk alerts found")
            return pl.DataFrame()

        latest_date = date_result[0]["LATEST_DATE"]
        logger.info(f"Querying alerts for date: {latest_date}")

        # Join predictions with PUDO metadata
        alerts_df = (
            predictions_df.filter((col("PREDICTION_DATE") == lit(latest_date)) & (col("PREDICTED_FILL_RATE") > 0.85))
            .join(pudo_ref_df, "PUDO_ID", "inner")
            .select(
                predictions_df["PUDO_ID"],
                pudo_ref_df["PUDO_NAME"],
                pudo_ref_df["PUDO_TYPE"],
                predictions_df["PREDICTION_DATE"],
                predictions_df["PREDICTED_FILL_RATE"],
                pudo_ref_df["CAPACITY"],
                (predictions_df["PREDICTED_FILL_RATE"] * pudo_ref_df["CAPACITY"])
                .cast("int")
                .alias("PREDICTED_OCCUPANCY"),
            )
            .sort(col("PREDICTED_FILL_RATE").desc())
        )

        # Convert to Pandas then Polars
        pandas_df = alerts_df.to_pandas()
        polars_df = pl.from_pandas(pandas_df)

        logger.info(f"Found {len(polars_df)} high-risk PUDOs")
        return polars_df

    except Exception as e:
        logger.error(f"Failed to get current alerts: {e}")
        raise
