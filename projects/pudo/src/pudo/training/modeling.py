from datetime import datetime, timedelta, timezone
import logging

from snowflake.core.task.context import TaskContext
from snowflake.ml.dataset import Dataset
from snowflake.ml.model import ModelVersion
from snowflake.snowpark import Session
from snowflake.snowpark.context import get_active_session
from snowflake.snowpark.table import Table
from xgboost import XGBRegressor

from pudo.core import packaging

logging.getLogger().setLevel(logging.ERROR)

logger = logging.getLogger(__name__)


def ensure_environment(session: Session, job_stage: str):
    """
    Ensure the environment is set up for pipeline execution.

    This function packages and uploads the pudo module to the job stage
    for use in remote ML job execution. It uploads both:
    1. As a zip file (for DAG imports parameter)
    2. As a directory structure (for submit_from_stage entrypoint)

    Note: Assumes the job_stage already exists (created by deployment scripts).

    Args:
        session (Session): Snowflake session object to configure
        job_stage (str): Job stage path (e.g., '@DATABASE.SCHEMA.JOB_STAGE')
    """
    # Package and upload the pudo module as zip (for DAG imports)
    packaging.package_and_upload_module(session=session, stage=job_stage)

    # Upload the pudo module as directory (for submit_from_stage)
    packaging.upload_module_as_directory(session=session, stage=job_stage)


def prepare_datasets(
    session: Session,
    name: str,
    version: str | None = None,
    *,
    source_table: Table,
    feature_store_name: str,
    feature_views: list[dict[str, str]] | None = None,
    split_config: dict[str, dict[str, str]] | None = None,
) -> tuple[Dataset, Dataset, Dataset, Dataset]:
    """
    Prepare datasets for training and evaluation with feature engineering and splitting.

    This function creates or loads datasets for machine learning, including feature engineering
    through the feature store. It handles both creation of new datasets and loading of existing
    ones, and automatically splits the data into training and test sets.

    Args:
        session (Session): Snowflake session object
        source_table (str): Name of the source table containing raw data
        name (str): Name for the dataset to create or load
        create_assets (bool, optional): Whether to create necessary assets if they don't exist.
            Defaults to False.
        force_refresh (bool, optional): Whether to force refresh by deleting existing datasets.
            Defaults to False.

    Returns:
        tuple[Dataset, Dataset, Dataset]: Tuple containing (full_dataset, train_dataset, test_dataset)
    """
    # Local import needed for functions run as task job
    from pudo.core.feature_store_helpers import (
        connect_to_feature_store,
        create_temporal_splits,
        generate_feature_dataset,
        get_dataset_split,
        get_feature_views,
    )

    if not split_config:
        split_config = create_temporal_splits(session, source_table=source_table)

    feature_store = connect_to_feature_store(session=session, name=feature_store_name)

    if not feature_views:
        # NOTE: This function runs remotely in Snowflake and cannot access local config files.
        # The caller MUST provide feature_views with versions loaded from local config.
        # Fallback: query all FVs and use latest version (not recommended for production)
        logger.warning(
            "No feature_views provided. Falling back to using all FVs with latest versions. "
            "This is not recommended for production - pass explicit versions from config instead."
        )
        feature_views = (
            feature_store.list_feature_views()
            .select(["NAME", "VERSION"])
            .group_by("NAME")
            .max("VERSION")
            .with_column_renamed("MAX(VERSION)", "VERSION")
            .to_pandas()
            .rename(columns={"NAME": "name", "VERSION": "version"})
            .to_dict("records")
        )

    feature_views = get_feature_views(feature_store=feature_store, feature_views=feature_views)

    ds = generate_feature_dataset(
        session=session,
        name=name,
        version=version,
        source_table=source_table,
        feature_store=feature_store,
        feature_views=feature_views,
    )

    train_ds = get_dataset_split(ds=ds, split_config=split_config, split_type="train")
    val_ds = get_dataset_split(ds=ds, split_config=split_config, split_type="validation")
    test_ds = get_dataset_split(ds=ds, split_config=split_config, split_type="test")

    return (ds, train_ds, val_ds, test_ds)


def train_and_evaluate_model(
    compute_pool: str,
    target_instances: int,
    stage_name: str,
    dataset_info: dict[str, dict],
    train_key: str,
    eval_keys: list[str],
    *,
    use_gpu: bool = False,
) -> tuple[XGBRegressor, dict[str, float]]:
    """
    Train and evaluate model using dataset keys.

    This function submits a training job using submit_from_stage() to execute
    the train_job.py script remotely on Snowpark Container Services.

    Args:
        compute_pool: Compute pool name for remote execution
        target_instances: Number of instances for distributed training
        stage_name: Stage where the module and script are uploaded
        dataset_info: Dictionary of serialized DatasetInfo objects (dict of dicts).
                     Keys: "ds", "train", "val", "test". Values: DatasetInfo as dicts.
        train_key: Key for the training dataset (e.g., "train")
        eval_keys: List of keys for evaluation datasets (e.g., ["val", "test"])
        use_gpu: Whether to use GPU for training

    Returns:
        Tuple of (trained_model, evaluation_metrics)
    """
    import json

    from snowflake.ml.jobs import submit_from_stage

    session = get_active_session()

    # dataset_info is already a dict of dicts (serialized DatasetInfo objects from prepare_datasets)
    # Serialize parameters as JSON strings for command-line arguments
    dataset_info_json = json.dumps(dataset_info)
    eval_keys_json = json.dumps(eval_keys)
    use_gpu_str = str(use_gpu)

    # Construct source path (MUST include @ prefix for StagePath recognition)
    # Strip trailing slash - Snowflake stage path regex doesn't allow it at the end
    source_path = f"{stage_name}/packages/pudo/training"

    # Submit the training job using the standalone script
    logger.info(f"Submitting training job from stage: {source_path}")
    job = submit_from_stage(
        source=source_path,
        compute_pool=compute_pool,
        entrypoint="train_job.py",
        stage_name=stage_name,
        target_instances=target_instances,
        session=session,
        # Pass parameters as command-line arguments (list of strings)
        args=[
            dataset_info_json,
            train_key,
            eval_keys_json,
            use_gpu_str,
        ],
    )

    logger.info(f"Training job submitted: {job.id}")

    # Wait for job completion
    logger.info("Waiting for training job to complete...")
    job.wait()

    logger.info("Training job completed successfully")

    # Get results from the job
    return job.result()


def register_model(
    session: Session,
    model: XGBRegressor,
    model_name: str,
    version_name: str,
    train_ds: Dataset,
    metrics: dict,
) -> ModelVersion:
    """
    Register a model in the model registry.

    This function registers a trained model in the Snowflake model registry with the specified
    name and version. It also associates the model with training data and performance metrics.

    Args:
        session (Session): Snowflake session object
        model (XGBClassifier): Trained XGBoost model to register
        model_name (str): Name for the model in the registry
        version_name (str): Version identifier for this model instance
        train_ds (Dataset): Training dataset used to train the model
        metrics (dict): Dictionary of performance metrics for the model

    Returns:
        ModelVersion: The registered model version object
    """
    # Local import needed for functions run as task job
    from pudo.core.environment import get_environment_from_context, get_registry_schema
    from pudo.training.ops import get_model_registry, register_model

    ctx = TaskContext(session)
    env = get_environment_from_context(ctx)
    registry = get_model_registry(session, schema=get_registry_schema(env))

    mv = register_model(
        session,
        model,
        model_name=model_name,
        version_name=version_name,
        train_data=train_ds,
        metrics=metrics,
        registry=registry,
    )
    logger.info(f"Registered model {mv.fully_qualified_model_name} version {mv.version_name}")

    return mv


def promote_model(session: Session, mv: ModelVersion) -> None:
    """
    Promote a model version to production.

    This function promotes a specific model version to production status in the model registry,
    making it the default version for inference operations.

    Args:
        session (Session): Snowflake session object
        mv (ModelVersion): Model version object to promote to production
    """
    # Local import needed for functions run as task job
    from pudo.core.environment import get_environment_from_context, get_registry_schema
    from pudo.training.ops import get_model_registry, promote_model

    ctx = TaskContext(session)
    env = get_environment_from_context(ctx)
    registry = get_model_registry(session, schema=get_registry_schema(env))

    promote_model(session, mv, registry=registry)
    logger.info(f"Promoted model {mv.fully_qualified_model_name} version {mv.version_name} to production")


def clean_up(session: Session, dataset_name: str, model_name: str, expiry_days: int = 7) -> None:
    """
    Clean up obsolete artifacts.

    This function removes obsolete model versions and dataset versions that are older than
    the specified expiry period. It helps maintain a clean workspace by removing outdated
    artifacts while preserving active models and datasets that are still in use.

    Args:
        session (Session): Snowflake session object
        dataset_name (str): Name of the dataset to clean up
        model_name (str): Name of the model to clean up
        expiry_days (int, optional): Number of days after which artifacts are considered obsolete.
            Defaults to 7.
    """
    # Local import needed for functions run as task job
    from pudo.core.environment import get_environment_from_context, get_registry_schema
    from pudo.training.ops import get_model_registry

    ctx = TaskContext(session)
    env = get_environment_from_context(ctx)
    registry_schema = get_registry_schema(env)

    # Use timezone-aware datetime for comparison
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=expiry_days)  # noqa: UP017

    # Delete obsolete models
    mr = get_model_registry(session, schema=registry_schema)
    try:
        model = mr.get_model(model_name=model_name)
        for _, mv_info in model.show_versions().iterrows():
            created_on = mv_info["created_on"]

            # Ensure created_on is timezone-aware
            if created_on.tzinfo is None:
                created_on = created_on.replace(tzinfo=timezone.utc)  # noqa: UP017

            if created_on < cutoff_date and mv_info["is_default_version"].lower() == "false":
                model.delete_version(mv_info["name"])
                logger.info(f"Deleted obsolete model version {mv_info['name']}")
    except ValueError:
        # Model doesn't exist yet (first run or previous tasks failed)
        logger.info(f"Model {model_name} not found, skipping model cleanup")

    # Delete obsolete datasets
    # Only consider the "main" dataset version, but retain any datasets where
    # the training split is still used by any active models.
    try:
        ds = Dataset.load(session, dataset_name)
        versions = ds.list_versions()
        for version in versions:
            dsv = ds.select_version(version)
            created_on = dsv.selected_version.created_on

            # Ensure created_on is timezone-aware
            if created_on.tzinfo is None:
                created_on = created_on.replace(tzinfo=timezone.utc)  # noqa: UP017

            if created_on < cutoff_date and not dsv.lineage("downstream", domain_filter={"model"}):
                ds.delete_version(version)
                logger.info(f"Deleted obsolete dataset version {version}")
    except Exception as e:
        # Dataset doesn't exist yet (first run or previous tasks failed)
        logger.info(f"Dataset {dataset_name} not found or error during cleanup: {e}")
