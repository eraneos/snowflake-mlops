# Tutorial 2: Repo Mental Model

This tutorial explains how the repository is structured so you know where things
live and why.

## What you will learn

- The hub-spoke architecture and ownership boundaries.
- What each top-level directory contains.
- How configuration and deployment work across components.

## The hub-spoke model

The repository is organised as a **hub** and one or more **project spokes**:

```
gls-snowflake-workshop/
├── hub/          # Shared platform infrastructure
├── mock_data/    # Data simulation and seeding
└── projects/
    └── pudo/     # Reference project: PUDO capacity prediction
```

### Ownership rule

> Hub and shared code may be referenced by projects. Projects may never be
> referenced by hub or shared code.

This means:

- The hub creates databases, schemas, roles, and warehouses that projects use.
- Each project owns its own feature views, training pipelines, and inference
  pipelines.
- Projects are independent of each other.

## Component breakdown

### `hub/`: Platform infrastructure

Creates the Snowflake objects that all projects share:

- Databases and schemas (`SHARED_DATA`, `FEATURE_STORE_<ENV>`,
  `MODEL_REGISTRY_<ENV>`).
- Operational roles and grants.
- Warehouses and compute pools.

Entry point: `make -C hub deploy-infra`

### `mock_data/`: Data simulation

Generates realistic PUDO data and loads it into `SHARED_DATA`:

- PUDO locations with geospatial attributes.
- Parcel volumes, delivery attempts, and occupancy.
- Temporal patterns and seasonal trends.

Entry points:

| Make target | What it does |
|---|---|
| `seed-shared-data` | Initial bulk load of PUDO data. |
| `add-morning-data` | Simulate morning parcel arrivals. |
| `add-evening-data` | Simulate evening delivery completions. |
| `simulation-status` | Show current simulation state. |
| `reset-simulation` | Reset simulation clock. |

### `projects/pudo/`: Reference project

The main MLOps project, organised into lifecycle blocks:

```
projects/pudo/
├── config/           # YAML configuration with environment overlays
├── scripts/          # Deployment and execution scripts
├── src/pudo/
│   ├── core/         # Shared utilities (session, config, SQL helpers)
│   ├── feature_view/ # Entity definitions and feature view implementations
│   ├── training/     # Training DAG, model training, evaluation
│   └── inference/    # Inference DAG, batch prediction, CLI tools
└── Makefile          # Operational entry points
```

Entry points:

| Make target | What it does |
|---|---|
| `deploy-schema` | Create the project schema in Snowflake. |
| `deploy-feature-store` | Register entities and feature views. |
| `deploy-training-dag` | Deploy the training task graph. |
| `run-training-dag` | Execute the training task graph. |
| `deploy-inference-dag` | Deploy the inference task graph. |
| `run-inference-dag` | Execute the inference task graph. |
| `run-inference` | Run batch inference via CLI. |
| `evaluate-predictions` | Compare predictions to actuals. |
| `inference-alerts` | Check for alert conditions. |
| `inference-summary` | Print prediction summary. |

## Configuration pattern

Each component uses YAML configuration with **environment overlays**:

```
config/
├── base.yaml              # Default values
├── dev.override.yaml      # Dev-specific overrides
├── staging.override.yaml  # Staging-specific overrides
└── prod.override.yaml     # Production-specific overrides
```

This is similar to Kustomize in Kubernetes: base values are merged with
environment-specific overrides. The active environment is determined by the
Git branch name.

## No root Makefile

There is intentionally no root `Makefile` or root `pyproject.toml`. Each
component is self-contained with its own:

- `pyproject.toml`: Python dependencies managed by uv.
- `Makefile`: Operational targets.
- `.env`: Snowflake connection credentials.
- `uv.lock`: Locked dependency tree.

You always run commands from within a component directory:

```bash
make -C hub deploy-infra
make -C mock_data seed-shared-data
make -C projects/pudo deploy-schema
```

## Next step

Continue to [Tutorial 3: Seed Shared Data](03-seed-shared-data.md) to
populate the shared Snowflake schema with mock PUDO data.
