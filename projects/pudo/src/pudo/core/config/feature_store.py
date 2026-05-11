"""Feature Store configuration with per-feature-view versioning.

Each feature view can have independent versions, enabling gradual rollout
and A/B testing of new features.

Auto-loads based on git branch (feat/* → dev, main → staging, v* → prod).
"""

from pydantic import BaseModel

from pudo.core.config.utils import load_yaml_config


class FeatureViewConfig(BaseModel):
    """Feature view configuration with independent versioning."""

    version: str
    enabled: bool = True
    description: str


class DeploymentConfig(BaseModel):
    """Deployment settings for feature store registration.

    Controls version immutability policy:
    - Dev: allow_version_overwrite=true (fast iteration)
    - Staging/Prod: allow_version_overwrite=false (immutable versions)
    """

    allow_version_overwrite: bool


class FeatureStoreConfig(BaseModel):
    """Feature store configuration with per-feature-view versioning.

    Enables independent evolution of feature views:
    - Historical features can be v1.2 while geospatial is v1.0
    - Dev can test v1.3 while prod uses stable v1.0
    - Feature views can be selectively disabled per environment

    Deployment settings control version immutability per environment.
    """

    feature_views: dict[str, FeatureViewConfig]
    deployment: DeploymentConfig  # Required - ensures explicit overwrite policy


config = load_yaml_config(FeatureStoreConfig, "feature_view/feature_store")
