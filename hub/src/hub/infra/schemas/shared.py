"""Bootstrap of the shared per-environment schemas owned by hub.

Per ADR-0004 the database carries:
- `SHARED_DATA`: env-agnostic, read-only source tables. Populated by the
  `mock_data/` component in this open-source repo and by upstream ingestion
  in real deployments.
- `FEATURE_STORE_<ENV>`: one Snowflake feature store schema per environment.
  Snowflake-ml's `FeatureStore(creation_mode=CREATE_IF_NOT_EXIST)` populates
  the FS metadata on first project deploy; this module only ensures the
  containing schema exists.
- `MODEL_REGISTRY_<ENV>`: one Snowflake ML model registry schema per
  environment. `Registry(...)` calls inside projects must pass
  `schema_name=MODEL_REGISTRY_<ENV>` explicitly per ADR-0004.

`<ENV>` values are `DEV`, `STAGING`, `PROD`. All three are created in one
pass; the bootstrap is idempotent.
"""

import logging

from snowflake.snowpark import Session

from hub.core.config import infra_config

logger = logging.getLogger(__name__)

ENVS = ("DEV", "STAGING", "PROD")


def bootstrap_shared_schemas(session: Session) -> None:
    db = infra_config.database.name
    shared = infra_config.shared_data

    logger.info("Creating schema %s.%s", db, shared.schema_name)
    session.sql(f"CREATE SCHEMA IF NOT EXISTS {db}.{shared.schema_name} COMMENT = '{shared.description}'").collect()

    for env in ENVS:
        fs_schema = f"FEATURE_STORE_{env}"
        logger.info("Creating schema %s.%s", db, fs_schema)
        session.sql(
            f"CREATE SCHEMA IF NOT EXISTS {db}.{fs_schema} "
            f"COMMENT = 'Snowflake feature store for env {env} (per ADR-0004).'"
        ).collect()

        registry_schema = f"MODEL_REGISTRY_{env}"
        logger.info("Creating schema %s.%s", db, registry_schema)
        session.sql(
            f"CREATE SCHEMA IF NOT EXISTS {db}.{registry_schema} "
            f"COMMENT = 'Snowflake ML model registry for env {env} (per ADR-0004).'"
        ).collect()
