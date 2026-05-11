from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import io
import json
import logging
from pathlib import Path
from typing import Any

import cloudpickle as cp
from snowflake.core.task.context import TaskContext
from snowflake.core.task.dagv1 import DAG, DAGTask, DAGTaskBranch
from snowflake.ml.data import DatasetInfo
from snowflake.ml.dataset import load_dataset
from snowflake.snowpark import Session

from pudo.core import packaging
from pudo.training import modeling

logging.getLogger().setLevel(logging.INFO)

logger = logging.getLogger(__name__)


def _ensure_environment(session: Session, dag_stage: str, job_stage: str):
    """
    Ensure the environment is properly set up for DAG execution.

    This function packages and uploads the pudo module to both the DAG stage
    (for DAG task execution) and job stage (for remote ML job execution).

    Note: Assumes both stages already exist (created by deployment scripts).

    Args:
        session (Session): Snowflake session object
        dag_stage (str): DAG stage path (e.g., '@DATABASE.SCHEMA.DAG_STAGE')
        job_stage (str): Job stage path (e.g., '@DATABASE.SCHEMA.JOB_STAGE')
    """
    # Package and upload the pudo module to DAG stage
    packaging.package_and_upload_module(session=session, stage=dag_stage)

    # Package and upload to job stage for remote ML jobs
    modeling.ensure_environment(session, job_stage)


@dataclass(frozen=True)
class RunConfig:
    run_id: str
    source_table: str  # Fully qualified table name (e.g., 'DATABASE.SCHEMA.TABLE')
    dataset_name: str
    feature_store: str
    model_name: str
    metric_name: str
    metric_threshold: float
    compute_pool: str
    job_stage: str
    dag_stage: str
    # Split configuration (individual fields instead of dict - DAG config limitation)
    train_days: int
    val_days: int
    test_days: int
    use_gpu: bool = False
    target_instances: int = 1
    dataset_version: str | None = None
    feature_views: str | None = None  # JSON string: [{"name": "...", "version": "..."}]

    @property
    def artifact_dir(self) -> Path:
        return Path(self.dag_stage) / "run_artifacts" / self.run_id

    @classmethod
    def from_task_context(cls, ctx: TaskContext, **kwargs: Any) -> "RunConfig":
        run_schedule = ctx.get_current_task_graph_original_schedule()
        run_id = "v" + (
            run_schedule.strftime("%Y%m%d_%H%M%S") if isinstance(run_schedule, datetime) else str(run_schedule)
        )
        run_config = {"run_id": run_id}

        graph_config = ctx.get_task_graph_config() or {}
        merged = run_config | graph_config | kwargs

        # Get expected fields from RunConfig
        expected_fields = set(cls.__annotations__)

        # Find unexpected keys
        unexpected_keys = [key for key in merged if key not in expected_fields]
        for key in unexpected_keys:
            logger.warning(f"Unexpected config key '{key}' will be ignored")

        filtered = {k: v for k, v in merged.items() if k in expected_fields}
        return cls(**filtered)

    @classmethod
    def from_session(cls, session: Session) -> "RunConfig":
        ctx = TaskContext(session)
        return cls.from_task_context(ctx)


def prepare_datasets(session: Session) -> str:
    """
    DAG task to prepare datasets for model training.

    This function is executed as part of the DAG workflow to prepare the training and test datasets.
    It retrieves the configuration from the task context and calls the shared prepare_datasets
    function to generate the necessary dataset splits.

    Args:
        session (Session): Snowflake session object

    Returns:
        str: JSON string containing serialized dataset information for downstream tasks
    """
    ctx = TaskContext(session)
    config = RunConfig.from_task_context(ctx)

    from pudo.training.modeling import prepare_datasets

    source_table = session.table(config.source_table)

    # Deserialize feature_views from JSON string
    feature_views_list = json.loads(config.feature_views) if config.feature_views else None

    # Build split_config from individual fields
    from pudo.core.feature_store_helpers import create_temporal_splits

    split_config = create_temporal_splits(
        session=session,
        source_table=source_table,
        train_days=config.train_days,
        val_days=config.val_days,
        test_days=config.test_days,
    )

    ds, train_ds, val_ds, test_ds = prepare_datasets(
        session=session,
        name=config.dataset_name,
        version=config.dataset_version,
        source_table=source_table,
        feature_store_name=config.feature_store,
        feature_views=feature_views_list,
        split_config=split_config,
    )

    dataset_info = {
        "ds": asdict(ds.read.data_sources[0]),
        "val": asdict(val_ds.read.data_sources[0]),
        "train": asdict(train_ds.read.data_sources[0]),
        "test": asdict(test_ds.read.data_sources[0]),
    }
    return json.dumps(dataset_info)


def train_model(session: Session) -> str:
    """
    DAG task to train a machine learning model.

    This function is executed as part of the DAG workflow to train a model using the prepared datasets.
    It retrieves dataset information from the previous task, trains the model, evaluates it on both
    training and test sets, and saves the model to a stage for later use.

    Args:
        session (Session): Snowflake session object

    Returns:
        str: JSON string containing model path and evaluation metrics
    """
    ctx = TaskContext(session)
    config = RunConfig.from_task_context(ctx)

    from pudo.training.modeling import train_and_evaluate_model

    # Get serialized dataset info (dict of dicts, passed as-is to remote handler)
    dataset_info_serialized = json.loads(ctx.get_predecessor_return_value("PREPARE_DATA"))

    # Train the model (deserialization to DatasetInfo happens inside remote handler)
    logger.info("Training and evaluating model...")
    model, metrics = train_and_evaluate_model(
        compute_pool=config.compute_pool,
        target_instances=config.target_instances,
        stage_name=config.job_stage,
        dataset_info=dataset_info_serialized,
        train_key="train",
        eval_keys=["val", "test"],
        use_gpu=config.use_gpu,
    )  # Returns tuple directly (job.result() is called inside train_and_evaluate_model)

    # Save model to stage and return the metrics as a JSON string
    logger.info("Saving model...")
    model_pkl = cp.dumps(model)
    model_path = Path(config.artifact_dir) / "model.pkl"
    # put_stream accepts stage_location as string only
    put_result = session.file.put_stream(io.BytesIO(model_pkl), str(model_path), overwrite=True)

    result_dict = {
        # PosixPath is not serializable
        "model_path": str(Path(config.artifact_dir) / put_result.target),
        "metrics": metrics,
    }
    return json.dumps(result_dict)


def check_model_quality(session: Session) -> str:
    """
    DAG task to check model quality and determine next action.

    This function evaluates the trained model's performance against a configured threshold
    and returns the appropriate next action for the DAG workflow. If the model meets the
    quality threshold, it returns "promote_model", otherwise "send_alert".

    Args:
        session (Session): Snowflake session object

    Returns:
        str: "promote_model" if model meets threshold, "send_alert" otherwise
    """
    ctx = TaskContext(session)
    config = RunConfig.from_task_context(ctx)

    metrics = json.loads(ctx.get_predecessor_return_value("TRAIN_MODEL"))["metrics"]

    # If model is good, promote model
    threshold = config.metric_threshold
    if metrics[config.metric_name] <= threshold:
        return "promote_model"
    return "send_alert"


def promote_model(session: Session) -> str:
    """
    DAG task to promote a trained model to production.

    This function registers the trained model in the model registry and promotes it
    to production status. It retrieves the model from the stage, loads the dataset
    information, and uses the model pipeline functions to complete the promotion.

    Args:
        session (Session): Snowflake session object

    Returns:
        str: Tuple of (fully_qualified_model_name, version_name) as string
    """
    ctx = TaskContext(session)
    config = RunConfig.from_task_context(ctx)

    from pudo.training.modeling import promote_model, register_model

    # Load the model
    train_result = json.loads(ctx.get_predecessor_return_value("TRAIN_MODEL"))
    model_path = train_result["model_path"]
    with session.file.get_stream(model_path, decompress=True) as stream:
        model = cp.loads(stream.read())

    serialized = json.loads(ctx.get_predecessor_return_value("PREPARE_DATA"))
    source_data = {key: DatasetInfo(**obj_dict) for key, obj_dict in serialized.items()}
    mv = register_model(
        session,
        model,
        model_name=config.model_name,
        version_name=config.run_id,
        train_ds=load_dataset(
            session,
            source_data["train"].fully_qualified_name,
            source_data["train"].version,
        ),
        metrics=train_result["metrics"],
    )

    promote_model(session, mv)

    return json.dumps({"model_name": mv.fully_qualified_model_name, "model_version": mv.version_name})


def send_alert(session: Session) -> str:
    """
    DAG task to send alerts when model quality is below threshold.

    This is a dummy notification task that would integrate with external notification
    services (e.g., email, Slack, PagerDuty) in a production environment.

    NOTE: In production, you could integrate notification services here:
    - Email alerts via SMTP or cloud email services (SendGrid, AWS SES)
    - Slack/Teams notifications via webhooks
    - PagerDuty/Opsgenie for incident management
    - Dashboard alerts for ML monitoring platforms (MLflow, Weights & Biases)
    - Data quality monitoring systems (Great Expectations, Monte Carlo)

    Args:
        session (Session): Snowflake session object

    Returns:
        str: JSON string containing alert details
    """
    ctx = TaskContext(session)
    config = RunConfig.from_task_context(ctx)

    # Get model metrics from train_model task
    train_result = json.loads(ctx.get_predecessor_return_value("TRAIN_MODEL"))
    metrics = train_result.get("metrics", {})

    metric_value = metrics.get(config.metric_name)
    threshold = config.metric_threshold

    logger.warning(f"⚠️  Model quality alert: {config.metric_name}={metric_value:.4f} exceeds threshold {threshold:.4f}")
    logger.warning(f"Model: {config.model_name} (version: {config.run_id})")
    logger.warning("Model was NOT promoted to production")
    logger.warning("📧 [Notification system would trigger here]")

    # Dummy notification logic - would send actual alerts in production
    alert_details = {
        "alert_type": "model_quality_threshold_exceeded",
        "model_name": config.model_name,
        "model_version": config.run_id,
        "metric_name": config.metric_name,
        "metric_value": metric_value,
        "threshold": threshold,
        "action": "model_not_promoted",
    }

    logger.info(f"Alert details: {alert_details}")

    return json.dumps(alert_details)


def cleanup(session: Session) -> None:
    """
    DAG task to clean up temporary artifacts and obsolete resources.

    This function is executed as a finalizer task in the DAG workflow to clean up
    temporary files, artifacts, and obsolete dataset/model versions. It removes
    the artifact directory from the stage and calls the shared cleanup function.

    Args:
        session (Session): Snowflake session object
    """
    ctx = TaskContext(session)
    config = RunConfig.from_task_context(ctx)

    from pudo.training.modeling import clean_up

    session.sql(f"REMOVE {config.artifact_dir}").collect()
    clean_up(session, config.dataset_name, config.model_name)


def create_dag(
    name: str,
    warehouse: str,
    stage_location: str,
    dag_stage: str,
    job_stage: str,
    data_table: str,
    schedule: timedelta | None = None,
    **config: dict[str, Any],
) -> DAG:
    """
    Create a DAG for the machine learning model training workflow.

    This function creates a complete DAG that includes data preparation, model training,
    quality checking, model promotion, and cleanup tasks. The DAG is configured with
    the necessary packages and stages for execution.

    Args:
        name (str): Name of the DAG
        warehouse (str): Warehouse for DAG execution
        stage_location (str): Stage location for DAG artifacts
        dag_stage (str): Fully qualified DAG stage path (e.g., '@DATABASE.SCHEMA.DAG_STAGE')
        job_stage (str): Fully qualified job stage path (e.g., '@DATABASE.SCHEMA.JOB_STAGE')
        data_table (str): Fully qualified source table name
        schedule (Optional[timedelta], optional): Schedule interval for the DAG.
            Defaults to None (no schedule).
        **config (Any): Additional configuration parameters to override defaults

    Returns:
        DAG: Configured DAG object ready for deployment
    """
    with DAG(
        name,
        warehouse=warehouse,
        schedule=schedule,
        use_func_return_value=True,
        stage_location=stage_location,
        packages=packaging.get_packages_from_pyproject(),
        imports=[f"{dag_stage}/packages/pudo.zip"],
        config={
            "source_table": data_table,
            "dataset_name": "PUDO_OCCUPANCY",
            "model_name": "PUDO__CAPACITY_MODEL",
            "metric_name": "test_mean_squared",
            "metric_threshold": 0.7,
            "dag_stage": dag_stage,
            "job_stage": job_stage,
            **config,  # Contains feature_store_name and other runtime params from unified config
        },
    ) as dag:
        # Need to wrap first function in a DAGTask to make >> operator work properly
        prepare_data = DAGTask("prepare_data", definition=prepare_datasets)
        evaluate_model = DAGTaskBranch("check_model_quality", definition=check_model_quality)
        promote_model_task = DAGTask("promote_model", definition=promote_model)
        send_alert_task = DAGTask("send_alert", definition=send_alert)
        DAGTask("cleanup_task", definition=cleanup, is_finalizer=True)

        # Build the DAG with conditional branching
        # After model quality check, either promote the model (if good) or send alert (if poor)
        prepare_data >> train_model >> evaluate_model >> promote_model_task
        evaluate_model >> send_alert_task

    return dag
