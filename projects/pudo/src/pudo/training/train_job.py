"""
Standalone training script for remote execution via submit_from_stage().

This script contains the training logic that will be executed remotely
on Snowpark Container Services. It's designed to be uploaded as a directory
structure and executed via submit_from_stage().
"""

import logging
from typing import Any

from sklearn.metrics import mean_squared_error
from snowflake.ml.data import DataConnector, DataSource
from snowflake.snowpark import Session
from snowflake.snowpark.context import get_active_session
from xgboost import XGBRegressor

logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger(__name__)


def train_model(session: Session, input_data: DataSource, *, use_gpu: bool = False) -> XGBRegressor:
    """
    Train a model on the training dataset.

    This function trains an XGBoost classifier on the provided training data. It extracts
    features and labels from the input data, configures the model with predefined parameters,
    and trains the model. This function is executed remotely on Snowpark Container Services.

    Args:
        session (Session): Snowflake session object
        input_data (DataSource): Data source containing training data with features and labels
        use_gpu (bool): Whether to use GPU for training

    Returns:
        XGBRegressor: Trained XGBoost regressor model
    """
    logger.info("Loading data...")
    input_data_df = DataConnector.from_sources(session, [input_data]).to_pandas()

    exclude_cols = input_data.exclude_cols
    label_col = exclude_cols[0]

    X_train = input_data_df.drop(exclude_cols, axis=1)
    y_train = input_data_df[label_col].squeeze()

    logger.info("Setting model parameter...")
    model_params = {
        "max_depth": 50,
        "n_estimators": 100,
        "learning_rate": 0.75,
        "objective": "reg:logistic",
        "booster": "gbtree",
    }

    # Distributed training - use ML Runtime distributor APIs
    from snowflake.ml.modeling.distributors.xgboost.xgboost_estimator import (
        XGBEstimator,
        XGBScalingConfig,
    )

    estimator = XGBEstimator(
        params=model_params,
        scaling_config=XGBScalingConfig(use_gpu=use_gpu),
    )

    logger.info("Training model...")
    estimator.fit(X_train, y_train)

    # Convert distributed estimator to standard XGBClassifier is needed
    # as the distributed XGBEstimator is unserializable.
    return getattr(estimator, "_sklearn_estimator", estimator)


def evaluate_model(
    session: Session,
    model: XGBRegressor,
    input_data: DataSource,
    *,
    prefix: str | None = None,
) -> dict:
    """
    Evaluate a model on the training and test datasets.

    This function evaluates a trained model's performance by calculating various metrics
    including F1 score, accuracy, precision, and recall. It can optionally add a prefix
    to metric names to distinguish between training and test metrics.

    Args:
        session (Session): Snowflake session object
        model (XGBClassifier): Trained XGBoost model to evaluate
        input_data (DataSource): Data source containing evaluation data with features and labels
        prefix (str, optional): Prefix to add to metric names (e.g., "train_", "test_").
            Defaults to None.

    Returns:
        dict: Dictionary containing evaluation metrics with metric names as keys and scores as values
    """
    input_data_df = DataConnector.from_sources(session, [input_data]).to_pandas()

    exclude_cols = input_data.exclude_cols
    label_col = exclude_cols[0]

    X_test = input_data_df.drop(exclude_cols, axis=1)
    expected = input_data_df[label_col].squeeze()
    actual = model.predict(X_test)

    metric_types = [mean_squared_error]

    metrics = {m.__name__.strip("_score"): round(m(expected, actual).tolist(), 4) for m in metric_types}

    if prefix:
        metrics = {f"{prefix}_{k}": v for k, v in metrics.items()}

    return metrics


def main(
    dataset_info: dict[str, dict],
    train_key: str,
    eval_keys: list[str],
    *,
    use_gpu: bool = False,
) -> tuple[Any, dict[str, float]]:
    """
    Main training handler executed remotely.

    Args:
        dataset_info: Dictionary of dataset configurations (keys: ds, train, val, test)
                     Each value is a dict representation of a DatasetInfo object
        train_key: Key for training dataset (e.g., "train")
        eval_keys: List of keys for evaluation datasets (e.g., ["val", "test"])
        use_gpu: Whether to use GPU for training

    Returns:
        Tuple of (trained_model, evaluation_metrics)
    """
    from snowflake.ml.data import DatasetInfo

    session = get_active_session()

    # Convert dict representations back to DatasetInfo objects
    dataset_info_objects = {key: DatasetInfo(**obj_dict) for key, obj_dict in dataset_info.items()}

    # Load training data using the provided key
    if train_key not in dataset_info_objects:
        msg = (
            f"Training key '{train_key}' not found in dataset_info. Available keys: {list(dataset_info_objects.keys())}"
        )
        raise ValueError(msg)

    train_data = dataset_info_objects[train_key]

    # Load evaluation datasets using the provided keys
    eval_data = {}
    for key in eval_keys:
        if key not in dataset_info_objects:
            msg = (
                f"Evaluation key '{key}' not found in dataset_info. Available keys: {list(dataset_info_objects.keys())}"
            )
            raise ValueError(msg)
        eval_data[key] = dataset_info_objects[key]

    logger.info("Training model...")
    estimator = train_model(session, train_data, use_gpu=use_gpu)

    logger.info("Evaluating model...")
    metrics = {}
    for key, val in eval_data.items():
        metrics.update(**evaluate_model(session, estimator, val, prefix=key))

    # Convert distributed estimator to sklearn estimator for serialization
    estimator = estimator.get_booster()

    logger.info(f"Final estimator type: {type(estimator)}")

    return estimator, metrics


# Entry point when executed as script
if __name__ == "__main__":
    import json
    import sys

    # Parse command-line arguments passed via submit_from_stage
    # Expected args: [dataset_info_json, train_key, eval_keys_json, use_gpu_str]
    if len(sys.argv) < 5:
        msg = f"Expected 4 arguments, got {len(sys.argv) - 1}"
        raise ValueError(msg)

    dataset_info = json.loads(sys.argv[1])
    train_key = sys.argv[2]
    eval_keys = json.loads(sys.argv[3])
    use_gpu = sys.argv[4].lower() == "true"

    logger.info(f"Parsed arguments: train_key={train_key}, eval_keys={eval_keys}, use_gpu={use_gpu}")

    # Run training
    result = main(
        dataset_info=dataset_info,
        train_key=train_key,
        eval_keys=eval_keys,
        use_gpu=use_gpu,
    )

    logger.info(f"Training completed successfully. Result type: {type(result)}")

    # For Snowflake ML Jobs to capture the result, we need to explicitly set it
    # The mljob_launcher.py expects __return__ variable to be set
    __return__ = result

    logger.info(f"Training completed. Model type: {type(result[0])}, Metrics: {result[1]}")
