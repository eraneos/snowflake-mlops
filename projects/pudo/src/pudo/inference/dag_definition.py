"""Inference DAG pipeline for PUDO capacity prediction.

This module provides a DAG-based inference pipeline that can be scheduled in Snowflake.
The pipeline generates predictions for pending dates and stores results in the PREDICTIONS table.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import logging
from typing import Any

from snowflake.core.task.context import TaskContext
from snowflake.core.task.dagv1 import DAG, DAGTask
from snowflake.ml.registry import Registry
from snowflake.snowpark import DataFrame, Session
from snowflake.snowpark.functions import col, concat_ws, current_timestamp, lit, to_date

from pudo.core import packaging
from pudo.core.environment import get_environment_from_context, get_registry_schema
from pudo.core.feature_store_helpers import connect_to_feature_store, get_feature_views
from pudo.inference.utils import get_latest_pending_date

logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger(__name__)


def _ensure_environment(session: Session, dag_stage: str):
    """Ensure the environment is properly set up for inference DAG execution.

    Args:
        session: Snowflake session object
        dag_stage: DAG stage path (e.g., '@DATABASE.SCHEMA.INFERENCE_DAG_STAGE')
    """
    # Package and upload the pudo module to DAG stage
    packaging.package_and_upload_module(session=session, stage=dag_stage)


@dataclass(frozen=True)
class InferenceRunConfig:
    """Configuration for inference DAG runs."""

    run_id: str
    model_name: str
    feature_store: str
    shared_data_schema: str
    database: str
    schema_name: str
    alert_threshold: float = 0.85
    use_latest_promoted: bool = True
    fallback_to_latest_version: bool = True
    feature_view_configs: str = "[]"  # JSON-serialized list of feature view configs

    @classmethod
    def from_task_context(cls, ctx: TaskContext, **kwargs: Any) -> "InferenceRunConfig":
        """Create config from task context."""
        run_schedule = ctx.get_current_task_graph_original_schedule()
        run_id = "v" + (
            run_schedule.strftime("%Y%m%d_%H%M%S") if isinstance(run_schedule, datetime) else str(run_schedule)
        )
        run_config = {"run_id": run_id}

        graph_config = ctx.get_task_graph_config() or {}
        merged = run_config | graph_config | kwargs

        # Get expected fields from InferenceRunConfig
        expected_fields = set(cls.__annotations__)

        # Find unexpected keys
        unexpected_keys = [key for key in merged if key not in expected_fields]
        for key in unexpected_keys:
            logger.warning(f"Unexpected config key '{key}' will be ignored")

        filtered = {k: v for k, v in merged.items() if k in expected_fields}
        return cls(**filtered)

    @classmethod
    def from_session(cls, session: Session) -> "InferenceRunConfig":
        """Create config from session."""
        ctx = TaskContext(session)
        return cls.from_task_context(ctx)


def get_pending_predictions(session: Session) -> str:
    """DAG task to check for pending prediction dates.

    This function uses Snowpark DataFrames to check for dates that have
    morning data but no predictions yet.

    Args:
        session: Snowflake session object

    Returns:
        str: JSON with pending_date (or null if none found)
    """
    ctx = TaskContext(session)
    config = InferenceRunConfig.from_task_context(ctx)

    logger.info("Checking for pending prediction dates...")

    # Use utility function for Pythonic approach
    pending_date = get_latest_pending_date(
        session=session,
        database=config.database,
        shared_data_schema=config.shared_data_schema,
        predictions_schema=config.schema_name,
    )

    if pending_date is None:
        logger.info("No pending predictions found - workflow will skip inference tasks")
        return json.dumps({"pending_date": None})

    logger.info(f"Found pending prediction date: {pending_date}")
    return json.dumps({"pending_date": str(pending_date)})


def load_model(session: Session) -> str:
    """DAG task to load the production model from the registry.

    This function loads either the promoted model or falls back to the latest version
    based on configuration.

    Args:
        session: Snowflake session object

    Returns:
        str: JSON string containing model version and pending date
    """
    ctx = TaskContext(session)
    config = InferenceRunConfig.from_task_context(ctx)

    # Check if there's a pending date from get_pending_predictions task
    pending_info = json.loads(ctx.get_predecessor_return_value("GET_PENDING_PREDICTIONS"))
    if pending_info["pending_date"] is None:
        logger.info("No pending predictions - skipping load_model")
        return json.dumps({"skipped": True})

    prediction_date = pending_info["pending_date"]
    logger.info(f"Loading model for prediction date: {prediction_date}")
    logger.info(f"Model: {config.model_name}")
    registry = Registry(session=session, schema_name=get_registry_schema(get_environment_from_context(ctx)))
    model_ref = registry.get_model(config.model_name)

    if config.use_latest_promoted:
        try:
            model_version = model_ref.default
            logger.info(f"✅ Loaded promoted model version: {model_version.version_name}")
        except Exception as e:
            if not config.fallback_to_latest_version:
                msg = f"No promoted model found for '{config.model_name}'"
                raise RuntimeError(msg) from e

            logger.warning(f"No promoted model found, falling back to latest version: {e}")
            versions = model_ref.show_versions()
            latest_version_name = versions.sort_values("creation_time", ascending=False).iloc[0]["name"]
            model_version = model_ref.version(latest_version_name)
            logger.info(f"✅ Loaded latest model version: {latest_version_name}")
    else:
        versions = model_ref.show_versions()
        latest_version_name = versions.sort_values("creation_time", ascending=False).iloc[0]["name"]
        model_version = model_ref.version(latest_version_name)
        logger.info(f"✅ Loaded latest model version: {latest_version_name}")

    result = {
        "model_version": model_version.version_name,
        "pending_date": prediction_date,
    }

    return json.dumps(result)


def generate_features(session: Session) -> str:
    """DAG task to generate feature dataset for the prediction date.

    This function creates features using the Feature Store with caching support.

    Args:
        session: Snowflake session object

    Returns:
        str: JSON string confirming feature generation
    """
    ctx = TaskContext(session)
    config = InferenceRunConfig.from_task_context(ctx)

    # Check if there's a pending date from get_pending_predictions task
    pending_info = json.loads(ctx.get_predecessor_return_value("GET_PENDING_PREDICTIONS"))
    if pending_info["pending_date"] is None:
        logger.info("No pending predictions - skipping generate_features")
        return json.dumps({"skipped": True})

    prediction_date = pending_info["pending_date"]

    logger.info(f"Generating features for {prediction_date}")

    # Connect to feature store and get feature views
    fs = connect_to_feature_store(
        session=session,
        name=config.feature_store,
        database=config.database,
        warehouse=session.get_current_warehouse(),
    )

    # Get feature view configurations from DAG config
    # Feature views are loaded and filtered in the deploy script to avoid import issues
    feature_view_configs = json.loads(config.feature_view_configs)
    logger.info(f"Loaded {len(feature_view_configs)} feature view configs from DAG config")

    feature_views = get_feature_views(fs, feature_view_configs)
    logger.info(f"Using {len(feature_views)} feature views")

    # Create spine for prediction date (all PUDOs for that date)
    spine_df = (
        session.table(f"{config.database}.{config.shared_data_schema}.PUDO_REFERENCE")
        .select("PUDO_ID")
        .with_column("DATE", to_date(lit(prediction_date)))
    )

    logger.info(f"Created spine with {spine_df.count()} PUDO locations")

    # Generate dataset for this prediction date
    logger.info("Generating feature dataset...")
    dataset_name = f"INFERENCE_FEATURES_{prediction_date.replace('-', '')}"

    try:
        from snowflake.ml import dataset as ml_dataset
        from snowflake.ml._internal.exceptions.dataset_errors import DatasetNotExistError

        ds = ml_dataset.Dataset.load(session=session, name=dataset_name)
        ds = ds.select_version("v1")
        logger.info(f"✅ Loaded existing dataset: {dataset_name}")
    except DatasetNotExistError:
        logger.info(f"Creating new dataset: {dataset_name}")
        ds = fs.generate_dataset(
            name=session.get_fully_qualified_name_if_possible(dataset_name),
            version="v1",
            spine_df=spine_df.cache_result(),
            features=list(feature_views.values()),
            spine_timestamp_col="DATE",
        )
        logger.info(f"✅ Created dataset: {dataset_name}")

    result = {
        "dataset_name": dataset_name,
        "pending_date": prediction_date,
        "pudo_count": spine_df.count(),
    }

    return json.dumps(result)


def add_prediction_metadata(predictions_df: DataFrame, prediction_date: str, model_version: str) -> DataFrame:
    """Add metadata columns to predictions DataFrame.

    This function processes model predictions by adding essential metadata columns
    required for storage and tracking. It identifies the prediction output column,
    renames it to PREDICTED_FILL_RATE, and adds metadata including prediction ID,
    date, model version, timestamp, and placeholder columns for actual values.

    Args:
        predictions_df: DataFrame containing model predictions with PUDO_ID column
        prediction_date: Date for which predictions were made (YYYY-MM-DD format)
        model_version: Model version object used for generating predictions

    Returns:
        DataFrame: The enriched predictions DataFrame with metadata columns added

    Raises:
        ValueError: If no prediction output column is found in the predictions DataFrame
    """

    # Find the prediction output column
    output_col = None
    for col_name in predictions_df.columns:
        col_upper = col_name.upper().strip('"')
        if col_upper.startswith("OUTPUT") or "PREDICT" in col_upper:
            output_col = col_name
            break

    if output_col is None:
        msg = f"Expected prediction output column not found in: {predictions_df.columns}"
        raise ValueError(msg)

    logger.info(f"Using prediction column: {output_col}")

    # Add metadata columns
    # Note: PREDICTION_ID should be unique integer, PREDICTION_DATE should be DATE type
    from snowflake.snowpark.functions import hash as snowpark_hash

    return (
        predictions_df.with_column("PREDICTION_DATE", to_date(lit(prediction_date)))
        .with_column("MODEL_VERSION", lit(model_version.version_name))
        # Generate unique integer ID by hashing PUDO_ID and date string
        .with_column(
            "PREDICTION_ID",
            snowpark_hash(concat_ws(lit("_"), col("PUDO_ID"), lit(str(prediction_date)))),
        )
        .with_column_renamed(output_col, "PREDICTED_FILL_RATE")
        .with_column("PREDICTION_TIMESTAMP", current_timestamp())
        .with_column("ACTUAL_FILL_RATE", lit(None).cast("float"))
        .with_column("PREDICTION_ERROR", lit(None).cast("float"))
        .select(
            [
                "PREDICTION_ID",
                "PUDO_ID",
                "PREDICTION_DATE",
                "PREDICTED_FILL_RATE",
                "MODEL_VERSION",
                "PREDICTION_TIMESTAMP",
                "ACTUAL_FILL_RATE",
                "PREDICTION_ERROR",
            ]
        )
    )


def make_predictions(session: Session) -> str:
    """DAG task to generate predictions and save to PREDICTIONS table.

    This function runs model inference and stores predictions with metadata.

    Args:
        session: Snowflake session object

    Returns:
        str: JSON string containing prediction statistics
    """
    ctx = TaskContext(session)
    config = InferenceRunConfig.from_task_context(ctx)

    # Get feature dataset info from generate_features task
    features_result = json.loads(ctx.get_predecessor_return_value("GENERATE_FEATURES"))
    if features_result.get("skipped"):
        logger.info("No pending predictions - skipping make_predictions")
        return json.dumps({"skipped": True})

    dataset_name = features_result["dataset_name"]
    prediction_date = features_result["pending_date"]

    # Get model version from load_model task
    load_result = json.loads(ctx.get_predecessor_return_value("LOAD_MODEL"))
    if load_result.get("skipped"):
        logger.info("load_model was skipped - skipping make_predictions")
        return json.dumps({"skipped": True})

    model_version_name = load_result["model_version"]

    logger.info(f"Making predictions for {prediction_date}")
    logger.info(f"Using model version: {model_version_name}")

    # Load feature dataset
    from snowflake.ml import dataset as ml_dataset

    ds = ml_dataset.Dataset.load(session=session, name=dataset_name)
    ds = ds.select_version("v1")
    feature_df = ds.read.to_snowpark_dataframe()

    # Load model and run predictions
    registry = Registry(session=session, schema_name=get_registry_schema(get_environment_from_context(ctx)))
    model_ref = registry.get_model(config.model_name)
    model_version = model_ref.version(model_version_name)

    logger.info("Running model inference...")
    predictions_df = model_version.run(feature_df, function_name="predict")

    # Add metadata to predictions
    predictions_df = add_prediction_metadata(predictions_df, prediction_date, model_version)

    # Count total predictions
    total_count = predictions_df.count()
    logger.info(f"Generated {total_count} predictions")

    # Count high-capacity alerts
    high_capacity_count = predictions_df.filter(col("PREDICTED_FILL_RATE") > config.alert_threshold).count()

    # Save to PREDICTIONS table
    logger.info(f"Saving predictions to {config.database}.{config.schema_name}.PREDICTIONS...")
    predictions_df.write.mode("append").save_as_table(f"{config.database}.{config.schema_name}.PREDICTIONS")

    stats = {
        "prediction_date": prediction_date,
        "predictions_generated": total_count,
        "high_capacity_alerts": high_capacity_count,
        "model_version": model_version.version_name,
        "alert_threshold": config.alert_threshold,
    }

    logger.info(f"✅ Predictions saved: {stats}")
    return json.dumps(stats)


def send_high_capacity_alerts(session: Session) -> str:
    """DAG task to send alerts for high-capacity predictions.

    This is a dummy notification task that would integrate with external notification
    services (e.g., email, Slack, PagerDuty, SMS) in a production environment.

    NOTE: In production, you could integrate notification services here:
    - Email alerts via SMTP or cloud email services (SendGrid, AWS SES)
    - Slack/Teams notifications via webhooks
    - PagerDuty/Opsgenie for incident management
    - SMS alerts via Twilio
    - Custom dashboard alerts

    Args:
        session: Snowflake session object

    Returns:
        str: JSON string containing alert statistics
    """
    ctx = TaskContext(session)
    config = InferenceRunConfig.from_task_context(ctx)

    # Get prediction results from make_predictions task
    predictions_result = json.loads(ctx.get_predecessor_return_value("MAKE_PREDICTIONS"))
    if predictions_result.get("skipped"):
        logger.info("No predictions were made - skipping alerts")
        return json.dumps({"skipped": True})

    high_capacity_alerts = predictions_result.get("high_capacity_alerts", 0)
    prediction_date = predictions_result.get("prediction_date")
    total_predictions = predictions_result.get("predictions_generated", 0)

    logger.info(f"High capacity alert check for {prediction_date}")
    logger.info(f"Found {high_capacity_alerts} PUDOs above {config.alert_threshold} capacity threshold")

    # Dummy notification logic - would send actual alerts in production
    if high_capacity_alerts > 0:
        logger.info(f"⚠️  Would send alert: {high_capacity_alerts}/{total_predictions} PUDOs at risk")
        logger.info("📧 [Notification system would trigger here]")
    else:
        logger.info("✅ No high-capacity alerts - all PUDOs within normal range")

    return json.dumps(
        {
            "alerts_sent": high_capacity_alerts,
            "prediction_date": prediction_date,
            "alert_threshold": config.alert_threshold,
        }
    )


def cleanup_inference(session: Session) -> None:
    """DAG task to clean up temporary inference artifacts.

    This function is executed as a finalizer task in the DAG workflow.

    Args:
        session: Snowflake session object
    """
    logger.info("Inference cleanup completed")


def create_inference_dag(
    name: str,
    warehouse: str,
    stage_location: str,
    dag_stage: str,
    schedule: timedelta | None = None,
    **config: dict[str, Any],
) -> DAG:
    """Create a DAG for the inference pipeline with conditional execution.

    This function creates a complete inference DAG with branching logic for
    conditional execution and alerting.

    Args:
        name: Name of the DAG
        warehouse: Warehouse to use for task execution
        stage_location: Stage location for DAG artifacts (without @ prefix)
        dag_stage: Full DAG stage path (with @ prefix) for imports
        schedule: Schedule interval for the DAG (default: None for manual execution)
        **config: Additional configuration parameters

    Returns:
        DAG: Configured inference DAG object ready for deployment
    """
    with DAG(
        name,
        warehouse=warehouse,
        schedule=schedule,
        use_func_return_value=True,
        stage_location=stage_location,
        packages=[
            "snowflake-snowpark-python",
            "snowflake-ml-python<1.9.0",
            "pydantic>=2.0.0",
            "pydantic-settings>=2.0.0",
        ],
        imports=[f"{dag_stage}/packages/pudo.zip"],
        config=config,
    ) as dag:
        # Define tasks
        check_pending_task = DAGTask("get_pending_predictions", definition=get_pending_predictions)
        load_model_task = DAGTask("load_model", definition=load_model)
        generate_features_task = DAGTask("generate_features", definition=generate_features)
        make_predictions_task = DAGTask("make_predictions", definition=make_predictions)
        send_alerts_task = DAGTask("send_high_capacity_alerts", definition=send_high_capacity_alerts)

        # Cleanup task as finalizer (runs regardless of workflow outcome)
        DAGTask("cleanup_inference", definition=cleanup_inference, is_finalizer=True)

        # Build the DAG workflow with parallel execution
        # 1. Check for pending predictions (returns JSON with pending_date)
        # 2. Parallel execution: load_model and generate_features both check if pending_date exists
        # 3. make_predictions combines results from both parallel tasks
        # 4. send_high_capacity_alerts processes prediction results
        check_pending_task >> [load_model_task, generate_features_task]

        # Parallel branches converge at make_predictions
        # make_predictions waits for BOTH load_model and generate_features to complete
        load_model_task >> make_predictions_task
        generate_features_task >> make_predictions_task

        # Send alerts after predictions are made
        make_predictions_task >> send_alerts_task

    return dag
