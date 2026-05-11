"""Project-scoped feature store deployer for PUDO.

Opens the shared feature store at ``FEATURE_STORE_<ENV>`` (per ADR-0004),
registers the PUDO entity, and registers all ``PUDO__`` feature views via
``pudo.core.registry`` (per ADR-0002).

Hub does not deploy project feature views; each project owns its own deployer.
"""

import logging

from snowflake.ml.feature_store import CreationMode, FeatureStore

from pudo.core.config.feature_store import config as fs_config
from pudo.core.config.infrastructure import config as infra_config
from pudo.core.environment import detect_environment, get_feature_store_schema
from pudo.core.registry import derive_snowflake_name, get_feature_view_creator
from pudo.core.snowflake_session import create_session
from pudo.feature_view.entities.pudo_entity import create_pudo_entity

# Import feature view modules to trigger decorator registration
from pudo.feature_view.feature_views import (  # noqa: F401
    pudo_geospatial_features,
    pudo_historical_features,
    pudo_temporal_features,
)


class PUDOFeatureStore:
    def __init__(self):
        """Initialize PUDOFeatureStore using the project's hierarchical config."""
        self.logger = logging.getLogger(__name__)

        self.session = create_session()
        self.environment = detect_environment()
        self.fs = None
        self.entities = {}
        self.feature_views = {}

    def create_or_get_feature_store(self):
        """Create feature store if it doesn't exist, otherwise get existing one."""
        schema_name = get_feature_store_schema(self.environment)

        feature_store_kwargs = {
            "session": self.session,
            "database": infra_config.database.name,
            "name": schema_name,
            "creation_mode": CreationMode.CREATE_IF_NOT_EXIST,
            "default_warehouse": infra_config.warehouse.name,
        }

        self.fs = FeatureStore(**feature_store_kwargs)
        self.logger.info(f"Feature store ready: name={schema_name} db={infra_config.database.name}")

    def register_entities(self):
        """Register all entities."""
        pudo_entity = create_pudo_entity()
        self.entities["PUDO"] = self.fs.register_entity(pudo_entity)

        self.logger.info("Entities registered successfully")

    def _version_exists(self, feature_view_name: str, version: str) -> bool:
        """Check if a feature view version already exists in the feature store."""
        try:
            self.fs.get_feature_view(name=feature_view_name, version=version)
            return True
        except Exception:
            return False

    def register_feature_views(self):
        """Register all feature views using per-feature-view versioning from config.

        Uses registry-based discovery to automatically find feature view creation functions.
        Config defines which feature views to register; no hardcoded mapping needed.
        """
        refresh_freq = None
        warehouse = infra_config.warehouse.name
        allow_overwrite = fs_config.deployment.allow_version_overwrite

        self.logger.info(f"Using refresh frequency: {refresh_freq}")
        self.logger.info(f"Using warehouse: {warehouse}")
        self.logger.info(
            f"Version overwrite policy: {allow_overwrite} (environment: {self.environment})"
        )

        for fv_config_key, fv_cfg in fs_config.feature_views.items():
            if not fv_cfg.enabled:
                self.logger.info(f"⏭️  {fv_config_key} disabled, skipping")
                continue

            fv_create_func = get_feature_view_creator(fv_config_key)
            if not fv_create_func:
                self.logger.warning(
                    f"⚠️  No creation function registered for {fv_config_key}. "
                    "Did you forget to add @register_feature_view decorator?"
                )
                continue

            fv_snowflake_name = derive_snowflake_name(fv_config_key)
            version = fv_cfg.version

            if not allow_overwrite and self._version_exists(fv_snowflake_name, version):
                self.logger.warning(
                    f"⚠️  {fv_config_key} v{version} already exists. "
                    f"Skipping registration (allow_version_overwrite=false for {self.environment})"
                )
                self.feature_views[fv_snowflake_name] = self.fs.get_feature_view(
                    name=fv_snowflake_name, version=version
                )
                self.logger.info(f"✅ {fv_config_key} loaded (existing v{version})")
                continue

            self.logger.info(f"Creating {fv_config_key} (version {version})...")
            feature_view = fv_create_func(self.session, self.entities, refresh_freq, warehouse)

            self.logger.info(
                f"Registering {fv_config_key} (version {version}, overwrite={allow_overwrite})..."
            )
            self.feature_views[fv_snowflake_name] = self.fs.register_feature_view(
                feature_view=feature_view, version=version, overwrite=allow_overwrite
            )
            self.logger.info(f"✅ {fv_config_key} registered (version {version})")

        self.logger.info("All feature views processed successfully")

    def setup_complete_feature_store(self):
        """Complete setup of feature store."""
        self.create_or_get_feature_store()
        self.register_entities()
        self.register_feature_views()

        self.logger.info("Feature store setup completed successfully!")
        return self.fs, self.entities, self.feature_views

    def delete_feature_store(self):
        """Delete the feature store: remove feature views, entities, drop schema."""
        try:
            self.logger.info("Starting feature store deletion...")

            schema_name = get_feature_store_schema(self.environment)

            self.fs = FeatureStore(
                session=self.session,
                database=infra_config.database.name,
                name=schema_name,
                default_warehouse=infra_config.warehouse.name,
                creation_mode=CreationMode.FAIL_IF_NOT_EXIST,
            )

            if hasattr(self, "feature_views") and self.feature_views:
                self.logger.info("Deleting feature views...")
                for fv_name, fv in self.feature_views.items():
                    try:
                        self.fs.delete_feature_view(fv)
                        self.logger.info(f"✅ Deleted feature view: {fv_name}")
                    except Exception as e:
                        self.logger.warning(f"Failed to delete feature view {fv_name}: {e}")
                self.feature_views.clear()

            if hasattr(self, "entities") and self.entities:
                self.logger.info("Deleting entities...")
                for entity_name, entity in self.entities.items():
                    try:
                        self.fs.delete_entity(entity)
                        self.logger.info(f"✅ Deleted entity: {entity_name}")
                    except Exception as e:
                        self.logger.warning(f"Failed to delete entity {entity_name}: {e}")
                self.entities.clear()

            self.logger.info(f"Dropping schema: {infra_config.database.name}.{schema_name}")
            drop_schema_sql = (
                f"DROP SCHEMA IF EXISTS {infra_config.database.name}.{schema_name} CASCADE"
            )

            try:
                self.session.sql(drop_schema_sql).collect()
                self.logger.info(
                    f"✅ Successfully dropped schema: {infra_config.database.name}.{schema_name}"
                )
            except Exception as e:
                self.logger.warning(
                    f"Failed to drop schema {infra_config.database.name}.{schema_name}: {e}"
                )

            self.logger.info("Feature store deletion completed successfully!")

        except Exception as e:
            self.logger.error(f"Error during feature store deletion: {e}")
            raise
