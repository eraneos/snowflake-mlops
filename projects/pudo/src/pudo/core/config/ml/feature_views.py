"""Feature-views configuration consumed by the ML pipelines."""

from pudo.core.config.ml_models import FeatureViewsConfig
from pudo.core.config.utils import load_yaml_config

config = load_yaml_config(FeatureViewsConfig, "feature_view/feature_views")
