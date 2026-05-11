# hub

Platform-level component of the hub-spoke Snowflake MLOps reference monorepo.

Owns the account-level Snowflake resources and the schema bootstrap that every project depends on:

- Database `OSS_SF_MLOPS`, role `OSS_SF_MLOPS_DEVELOPER`, warehouse `OSS_SF_MLOPS_WH`, compute pool `OSS_SF_MLOPS_POOL` (per ADR-0004 "Platform Resources").
- The shared schemas `SHARED_DATA`, `FEATURE_STORE_<ENV>`, and `MODEL_REGISTRY_<ENV>` (per ADR-0004).

Hub never references projects (per ADR-0001). Projects do not provision platform resources.

## Layout

- `src/hub/infra/account/bootstrap.py` — account-level resource bootstrap (database, role, warehouse, compute pool, grants).
- `src/hub/infra/schemas/shared.py` — shared per-environment schema bootstrap (`SHARED_DATA`, `FEATURE_STORE_<ENV>`, `MODEL_REGISTRY_<ENV>` for `DEV`/`STAGING`/`PROD`).
- `src/hub/infra/sql/` — SQL templates loaded by the account bootstrap (idempotent `CREATE ... IF NOT EXISTS`).
- `src/hub/core/` — minimal session, credentials, env-detection, and config-loader helpers (duplicated from project side per ADR-0001/ADR-0003; candidate for centralization once ADR-0020 lands).
- `config/infrastructure.yaml` — declarative resource names.
- `scripts/deploy_infra.py` — deploy entry point that runs the account bootstrap then the shared-schema bootstrap. Wrapped by `hub/Makefile` (per ADR-0012).

## Deploy

```sh
make -C hub deploy-infra
```

Idempotent. Requires `ACCOUNTADMIN` to bootstrap account-level objects; the bootstrap-vs-ops role handoff is open under ADR-0013 (proposed). Cross-component sequence is documented in the root `README.md`.
