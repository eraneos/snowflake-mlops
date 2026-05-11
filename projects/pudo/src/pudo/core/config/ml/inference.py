"""Inference pipeline configuration."""

from pudo.core.config.ml_models import InferenceConfig
from pudo.core.config.utils import load_yaml_config

config = load_yaml_config(InferenceConfig, "inference")
