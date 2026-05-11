# projects/pudo

Example project demonstrating an end-to-end Snowflake-ml flow: feature view registration, training DAG, inference DAG (per ADR-0006). The PUDO capacity prediction problem is the baseline domain for the open-source repo.

PUDO is one of potentially many `projects/<name>/` spokes; the hub-spoke rule (ADR-0001) means hub does not reference this project, and this project does not reach into hub or other projects.

## Layout

Per ADR-0003 block layout:

- `src/pudo/feature_view/` — PUDO entity and feature view definitions.
- `src/pudo/training/` — training pipeline and training DAG.
- `src/pudo/inference/` — inference pipeline and inference DAG.
- `src/pudo/core/` — project-scoped utilities: snowpark session, env detection, config loader, packaging.
- `experiments/` — exploratory or experimental code (sibling of `src/`, not a Python package, per ADR-0003).
- `config/` — layered YAML config (Kustomize pattern; sibling of `src/`, per ADR-0003).
- `scripts/` — deploy entry points (per ADR-0012).
- `Makefile` — verb wrappers (per ADR-0012).

## Naming

- Models register as `PUDO__<MODEL>` in `MODEL_REGISTRY_<ENV>` (per ADR-0002 / ADR-0004).
- Feature views register as `PUDO__<FV_NAME>` in `FEATURE_STORE_<ENV>` (per ADR-0002).
- The project schema is `PUDO_<ENV>` (per ADR-0004).

## Deploy

```sh
make -C projects/pudo deploy-schema deploy-feature-store deploy-training-dag deploy-inference-dag
```

Cross-component sequence is documented in the root `README.md`.
