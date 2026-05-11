"""Training pipeline configuration."""

from pudo.core.config.ml_models import TrainingConfig
from pudo.core.config.utils import load_yaml_config

config = load_yaml_config(TrainingConfig, "training")
