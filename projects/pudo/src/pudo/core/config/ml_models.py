"""ML configuration module.

Unified ML configurations for feature views, training, and inference pipelines.
Auto-loads based on git branch (feat/* → dev, main → staging, v* → prod).

Note: Config files are organized under config/ml/ directory with subdirectories:
- config/ml/feature_views/ - Feature view definitions
- config/ml/training/ - Training pipeline settings
- config/ml/inference/ - Inference pipeline settings
"""

from datetime import timedelta

from pydantic import BaseModel, field_validator
from snowflake.core.task import Cron


def parse_schedule(value: str | None) -> timedelta | Cron | None:
    """Parse schedule string into timedelta or Cron object.

    Supported formats:
    - None: No scheduling (manual execution)
    - Timedelta: "1d" (1 day), "12h" (12 hours), "30m" (30 minutes)
    - CRON: "0 8 * * *" (daily at 8am UTC)
    - CRON with timezone: "0 8 * * * America/New_York"

    Args:
        value: Schedule string to parse

    Returns:
        timedelta, Cron, or None depending on input format

    Raises:
        ValueError: If the schedule format is invalid
    """
    if value is None:
        return None

    # Check if it's a CRON expression (contains spaces or asterisks)
    if " " in value or "*" in value:
        try:
            # Parse CRON format with optional timezone
            parts = value.rsplit(" ", 5)

            # Check if last part is a timezone (contains / or is uppercase)
            if len(parts) == 6 and ("/" in parts[5] or parts[5].isupper()):
                # CRON with timezone: "0 8 * * * America/New_York"
                cron_expr = " ".join(parts[:5])
                timezone = parts[5]
                return Cron(cron_expr, timezone)
            if len(parts) == 5:
                # CRON without timezone (uses UTC by default)
                return Cron(value, "UTC")

            msg = f"Invalid CRON format: {value}. Expected 5 fields (or 6 with timezone)"
            raise ValueError(msg)
        except Exception as e:
            msg = f"Failed to parse CRON expression '{value}': {e}"
            raise ValueError(msg) from e

    # Otherwise, treat as timedelta format
    import re

    if not re.match(r"^(\d+[dhm]|\d+)$", value):
        msg = (
            f"Invalid schedule format: {value}. Must be either:\n"
            "  - Timedelta: '1d', '12h', '30m'\n"
            "  - CRON: '0 8 * * *' or '0 8 * * * America/New_York'"
        )
        raise ValueError(msg)

    # Convert to timedelta
    try:
        if value.endswith("d"):
            return timedelta(days=int(value[:-1]))
        if value.endswith("h"):
            return timedelta(hours=int(value[:-1]))
        if value.endswith("m"):
            return timedelta(minutes=int(value[:-1]))
        return timedelta(days=int(value))
    except ValueError as e:
        msg = f"Could not convert {value} to a valid timedelta."
        raise ValueError(msg) from e


# ============================================================================
# Feature Views Configuration
# ============================================================================


class FeatureViewConfig(BaseModel):
    """Single feature view configuration with version pinning for ML pipelines."""

    version: str
    enabled: bool = True
    description: str
    snowflake_name: str  # Actual Snowflake feature view name (uppercase)


class FeatureViewsConfig(BaseModel):
    """Feature views configuration for ML pipelines.

    Defines which feature views to use and their pinned versions for reproducibility.
    This is the ML consumption config - feature_store config tracks latest available versions.
    """

    feature_views: dict[str, FeatureViewConfig]


# ============================================================================
# Training Pipeline Configuration
# ============================================================================


class TrainingPipelineConfig(BaseModel):
    """Training pipeline infrastructure configuration."""

    dag_name: str  # Name of the training DAG task
    job_stage: str  # Stage for ML job artifacts and model files
    dag_stage: str  # Stage for DAG definitions and packaged Python modules


class DatasetConfig(BaseModel):
    """Training dataset configuration."""

    name: str
    source_table: str
    train_days: int
    val_days: int
    test_days: int
    version: str | None = None  # Auto-generate if None


class ModelConfig(BaseModel):
    """Model configuration."""

    name: str


class ExecutionConfig(BaseModel):
    """Training execution configuration."""

    compute_pool: str  # Compute pool name from infrastructure.yaml
    use_gpu: bool
    target_instances: int
    schedule: timedelta | Cron | None  # Parsed schedule object (from YAML string)

    @field_validator("schedule", mode="before")
    @classmethod
    def parse_schedule_string(cls, v: str | timedelta | Cron | None) -> timedelta | Cron | None:
        """Parse schedule string into Snowflake schedule object.

        Args:
            v: Schedule value - can be string (from YAML), or already-parsed object

        Returns:
            Parsed schedule object (timedelta, Cron, or None)
        """
        # If already parsed (e.g., from reload), return as-is
        if isinstance(v, timedelta | Cron) or v is None:
            return v
        # Otherwise parse the string
        return parse_schedule(v)


class EvaluationConfig(BaseModel):
    """Model evaluation configuration."""

    metric_name: str
    metric_threshold: float  # Max allowed (lower is better for MSE)


class TrainingConfig(BaseModel):
    """Training pipeline configuration.

    Feature views are defined in FeatureViewsConfig.
    This config only contains training-specific settings.
    """

    pipeline: TrainingPipelineConfig
    dataset: DatasetConfig
    model: ModelConfig
    execution: ExecutionConfig
    evaluation: EvaluationConfig


# ============================================================================
# Inference Pipeline Configuration
# ============================================================================


class InferencePipelineConfig(BaseModel):
    """Inference pipeline infrastructure configuration."""

    dag_name: str  # Name of the inference DAG task
    dag_stage: str  # Stage for inference DAG definitions and packaged Python modules


class ModelSelectionConfig(BaseModel):
    """Model selection for inference."""

    name: str
    use_latest_promoted: bool
    fallback_to_latest_version: bool


class InferenceExecutionConfig(BaseModel):
    """Inference execution settings."""

    compute_pool: str  # Compute pool name from infrastructure.yaml
    schedule: timedelta | Cron | None  # Parsed schedule object (from YAML string)
    alert_threshold: float  # Alert when capacity predicted above this

    @field_validator("schedule", mode="before")
    @classmethod
    def parse_schedule_string(cls, v: str | timedelta | Cron | None) -> timedelta | Cron | None:
        """Parse schedule string into Snowflake schedule object.

        Args:
            v: Schedule value - can be string (from YAML), or already-parsed object

        Returns:
            Parsed schedule object (timedelta, Cron, or None)
        """
        # If already parsed (e.g., from reload), return as-is
        if isinstance(v, timedelta | Cron) or v is None:
            return v
        # Otherwise parse the string
        return parse_schedule(v)


class InferenceConfig(BaseModel):
    """Inference pipeline configuration.

    Feature views are defined in FeatureViewsConfig.
    This config only contains inference-specific settings.
    """

    pipeline: InferencePipelineConfig
    model: ModelSelectionConfig
    inference: InferenceExecutionConfig
