from datetime import date, datetime, timedelta
import logging

from snowflake.ml import dataset
from snowflake.ml._internal.exceptions.dataset_errors import DatasetNotExistError
from snowflake.ml._internal.utils.identifier import (
    parse_schema_level_object_identifier,
    resolve_identifier,
)
from snowflake.ml.feature_store import Entity, FeatureStore, FeatureView
from snowflake.snowpark import Session
from snowflake.snowpark.functions import col, lit, max as max_
from snowflake.snowpark.table import Table

logger = logging.getLogger(__name__)


def get_data_last_altered_timestamp(session: Session, source_table: Table) -> str:
    """
    Auto-generate dataset version from source table's last modification timestamp.

    This function queries the Snowflake INFORMATION_SCHEMA to find when a table was last modified
    and returns it in a version-friendly format suitable for dataset versioning.

    Usage Context:
    - Called when dataset version is not explicitly provided in config
    - Provides automatic versioning based on data freshness
    - Version changes only when source table is modified (INSERT, UPDATE, DELETE, ALTER)

    Version Format: "v%Y%m%d_%H%M%S" (e.g., v20250104_143052)
    - Sortable chronologically
    - Human-readable date/time
    - No special characters (compatible with Snowflake identifiers)

    Args:
        session: Snowflake session object
        source_table: Snowpark Table representing the source table

    Returns:
        Version string based on table's LAST_ALTERED timestamp

    Raises:
        ValueError: If the table is not found in the database

    See Also:
        generate_feature_dataset() - Uses this for auto-versioning when version=None
        CLAUDE.md "Dataset Versioning & Reproducibility" - Full workflow documentation
    """
    table_name = source_table.table_name
    db, schema, table = (
        resolve_identifier(identifier) if identifier else identifier
        for identifier in parse_schema_level_object_identifier(table_name)
    )
    if db is None:
        db = session.get_current_database()
    if schema is None:
        schema = session.get_current_schema()

    if db is None:
        msg = "Database name could not be determined"
        raise ValueError(msg)
    if schema is None:
        msg = "Schema name could not be determined"
        raise ValueError(msg)
    if table is None:
        msg = "Table name could not be determined"
        raise ValueError(msg)

    table_info = session.sql(
        f"""
        SELECT LAST_ALTERED FROM {db}.INFORMATION_SCHEMA.TABLES
            WHERE TABLE_CATALOG = '{db.replace('"', "")}'
            AND TABLE_SCHEMA = '{schema.replace('"', "")}'
            AND TABLE_NAME = '{table}'
        """
    ).collect()

    if len(table_info) == 0:
        msg = f"Table {table_name} not found"
        raise ValueError(msg)
    last_altered = datetime.fromisoformat(str(table_info[0][0]))

    return last_altered.strftime("v%Y%m%d_%H%M%S")


def connect_to_feature_store(
    session: Session, name: str, database: str | None = None, warehouse: str | None = None
) -> FeatureStore:
    """
    Connect to an existing feature store.

    Args:
        session: Snowpark session
        config_path: Path to configuration file

    Returns:
        FeatureStore instance
    """
    if not database:
        database = session.get_current_database()

    if not warehouse:
        warehouse = session.get_current_warehouse()

    fs = FeatureStore(
        session=session,
        database=database,
        name=name,
        default_warehouse=warehouse,
    )

    logger.info(f"Connected to feature store: {name}")
    return fs


def get_feature_views(feature_store: FeatureStore, feature_views: list[dict[str, str]]) -> dict[str, FeatureView]:
    """
    Retrieve all feature views from the feature store.

    Args:
        fs: FeatureStore instance
        version: Version of feature views to retrieve

    Returns:
        Dictionary of feature view names to feature view objects
    """
    fvs = {}

    for fv in feature_views:
        try:
            fv_name = fv["name"]
            fv_version = fv["version"]
            fv = feature_store.get_feature_view(fv_name, fv_version)
            fvs[fv_name] = fv
            logger.info(f"Retrieved feature view: {fv_name}")
        except Exception as e:
            logger.warning(f"Could not retrieve feature view {fv_name}: {e}")

    return fvs


def get_entities(fs: FeatureStore, names: list[str]) -> dict[str, Entity]:
    """
    Retrieve entities from the feature store.

    Args:
        fs: FeatureStore instance

    Returns:
        Dictionary of entity names to entity objects
    """
    entities = {}

    for entity_name in names:
        try:
            entity = fs.get_entity(entity_name)
            entities[entity_name] = entity
            logger.info(f"Retrieved entity: {entity_name}")
        except Exception as e:
            logger.warning(f"Could not retrieve entity {entity_name}: {e}")

    return entities


def create_temporal_splits(
    session,
    source_table: Table,
    cutoff_date: str | None = None,
    train_days: int = 180,
    val_days: int = 30,
    test_days: int = 30,
    prediction_horizon: int = 0,  # same day prediction
) -> dict[str, dict[str, str]]:
    """
    Create temporal splits for time series forecasting using Snowpark DataFrames.

    Args:
        cutoff_date: Latest date to use for training (YYYY-MM-DD)
        train_days: Number of days for training
        val_days: Number of days for validation
        test_days: Number of days for testing
        prediction_horizon: Days ahead to predict (1 for next day)
    """
    if cutoff_date is None:
        # Get the latest date from occupancy data minus prediction horizon
        latest_date_row = source_table.select(max_(col("DATE")).alias("max_date")).collect()[0]
        latest_date = latest_date_row["MAX_DATE"]

        # Convert to datetime if it's a string or date object
        if isinstance(latest_date, str):
            latest_date = datetime.strptime(latest_date, "%Y-%m-%d")
        elif isinstance(latest_date, date) and not isinstance(latest_date, datetime):
            latest_date = datetime.combine(latest_date, datetime.min.time())

        cutoff_date = (latest_date - timedelta(days=prediction_horizon)).strftime("%Y-%m-%d")

    # Calculate split dates
    cutoff = datetime.strptime(cutoff_date, "%Y-%m-%d")

    # Test period (most recent)
    test_end = cutoff
    test_start = test_end - timedelta(days=test_days)

    # Validation period (before test)
    val_end = test_start - timedelta(days=prediction_horizon)
    val_start = val_end - timedelta(days=val_days)

    # Training period (before validation)
    train_end = val_start - timedelta(days=prediction_horizon)
    train_start = train_end - timedelta(days=train_days)

    splits = {
        "train": {"start_date": train_start.strftime("%Y-%m-%d"), "end_date": train_end.strftime("%Y-%m-%d")},
        "validation": {"start_date": val_start.strftime("%Y-%m-%d"), "end_date": val_end.strftime("%Y-%m-%d")},
        "test": {"start_date": test_start.strftime("%Y-%m-%d"), "end_date": test_end.strftime("%Y-%m-%d")},
    }

    logger.info("Temporal splits created:")
    logger.info(f"  Train: {splits['train']['start_date']} to {splits['train']['end_date']}")
    logger.info(f"  Validation: {splits['validation']['start_date']} to {splits['validation']['end_date']}")
    logger.info(f"  Test: {splits['test']['start_date']} to {splits['test']['end_date']}")

    return splits


def generate_feature_dataset(
    session: Session,
    name: str,
    version: str | None = None,
    *,
    source_table: Table,
    feature_store: FeatureStore,
    feature_views: dict[str, FeatureView],
):
    """
    Generate or load a feature dataset with point-in-time correctness.

    Dataset Versioning:
    - If version is None: Auto-generates from source table's last modified timestamp (e.g., v20250104_143052)
    - If version is provided: Uses explicit version (e.g., from config for reproducibility)

    Dataset Immutability:
    - Existing dataset versions are NEVER overwritten (idempotent loading)
    - If version exists: Loads and returns existing dataset
    - If version missing: Creates new dataset with that version
    - This ensures version immutability for reproducibility

    Usage:
    - Dev/Staging: Pass version=None for auto-generation (flexible iteration)
    - Production: Pass explicit version from config (pinned for reproducibility)

    See CLAUDE.md "Dataset Versioning & Reproducibility" for workflow details.

    Args:
        session: Snowpark session
        name: Dataset name (e.g., "PUDO_OCCUPANCY_DATASET")
        version: Dataset version string or None for auto-generation
        source_table: Source data table for spine generation
        feature_store: Feature store instance
        feature_views: Dict of feature views to include

    Returns:
        Dataset instance with selected version
    """
    # Create spine DataFrame for the feature date range
    logger.info("Creating spine for data...")

    spine_df = (
        source_table.select(col("PUDO_ID"), col("DATE"), col("FILL_RATE")).distinct().sort(col("PUDO_ID"), col("DATE"))
    )

    # Get features from all feature views
    logger.info("Retrieving features for data...")

    # Generate dataset with point-in-time correctness
    # Version determination: config-provided (explicit) or auto-generated (source table timestamp)
    version = version or get_data_last_altered_timestamp(session, source_table)

    # Idempotent loading: Try to load existing dataset version first (immutability guarantee)
    try:
        ds = dataset.Dataset.load(
            session=session,
            name=name,
        )
        ds = ds.select_version(
            version=version,
        )
        logger.info(f"Existing dataset version '{version}' loaded (immutable, not regenerated)")
    except DatasetNotExistError:
        logger.info(f"Generating new dataset version '{version}'")
        ds = feature_store.generate_dataset(
            name=session.get_fully_qualified_name_if_possible(name),
            version=version,
            spine_df=spine_df.cache_result(),
            features=feature_views.values(),
            spine_timestamp_col="DATE",
            spine_label_cols=["FILL_RATE"],
        )

    logger.info("Dataset ready.")

    return ds


def get_dataset_split(
    ds: dataset.Dataset,
    split_config: dict,
    split_type: str = "train",
):
    """
    Get dataset for a specific split using Snowpark DataFrames.
    """
    # Read the dataset into a Snowpark DataFrame and apply any transformations
    df = ds.read.to_snowpark_dataframe()

    split_info = split_config[split_type]

    # Date range
    start = split_info["start_date"]
    end = split_info["end_date"]

    # Create spine DataFrame for the date range
    logger.info(f"Creating split for {split_type}...")

    split_df = df.filter((col("DATE") >= lit(start)) & (col("DATE") <= lit(end)))

    version = f"{ds.selected_version.name}_{split_type}"

    try:
        split_ds = ds.select_version(version)
    except Exception:
        # Convert DATE column to VARCHAR to avoid schema inference issues in remote execution
        # The DATE type can cause problems when Snowflake tries to infer schema from dataframes
        from snowflake.snowpark.functions import to_varchar

        split_df_with_varchar = split_df.with_column("DATE", to_varchar(col("DATE")))

        split_ds = ds.create_version(
            version=f"{ds.selected_version.name}_{split_type}",
            input_dataframe=split_df_with_varchar.cache_result(),
            exclude_cols=ds.selected_version.exclude_cols,
            label_cols=ds.selected_version.label_cols,
            comment=f"{split_type} split for {ds.selected_version.name}",
        )

    return split_ds
