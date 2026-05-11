<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/brand/eraneos_wordmark_white.svg">
    <img src="docs/assets/brand/eraneos_wordmark_black.svg" alt="Eraneos" width="600">
  </picture>
</p>

# Snowflake MLOps Reference Monorepo

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://eraneos.github.io/snowflake-mlops/)

An open-source reference monorepo for end-to-end MLOps on Snowflake. The repo serves two complementary purposes:

1. **Show what end-to-end MLOps on Snowflake can look like for a realistic, multi-team setup.** Existing Snowflake ML material focuses on individual pieces of the workflow. This repo wires the different Snowflake-native MLOps features together. It uses a hub-spoke layout (central platform infrastructure plus team-owned project spokes) as one specific way to organize that example. Other layouts can solve the same problem; the patterns demonstrated here generalize.

2. **Showcase the breadth of Snowflake-native MLOps primitives and how they interact.** The repo exercises the Snowflake Feature Store, the Snowflake ML Model Registry, Snowflake Tasks DAGs for training and inference orchestration, native task observability (`TASK_HISTORY`, Account Usage), and the surrounding primitives (databases, schemas, warehouses, compute pools, roles, stages) that wire them together. Design choices default to Snowflake-native primitives over external tooling; external dependencies are introduced only when no native primitive exists or the native option is materially worse.

Everything is showcased through a single end-to-end example, drawn from a logistics and parcel-delivery context: predicting capacity utilisation at Pick-Up / Drop-Off points (PUDO), the network of shops, lockers, and service points where parcels are dropped off and collected. The example lives under `projects/pudo/`. All data for the example is synthetic and generated locally (see `mock_data/`), so the repo runs end-to-end on a fresh checkout without any real upstream data source. Audience: engineering teams adopting these patterns for production use.

## Layout

```
hub/                   # platform IaC: account-level resources, shared schemas
mock_data/             # SHARED_DATA fixtures (replaced by real ingestion in production)
feature_store/         # central SHARED__ feature views (placeholder at baseline)
projects/pudo/         # example project: feature views, training DAG, inference DAG
docs/                  # tutorials, concepts, guides, reference
```

The repo root has no `pyproject.toml` and no `Makefile`. Each component is independently locked and orchestrated.

The architectural rule that constrains every layout choice: hub and shared code may be referenced by projects; projects may never be referenced by hub or shared code.

## Prerequisites

- Snowflake account. `ACCOUNTADMIN` (or `SECURITYADMIN`) is required for the one-time hub bootstrap that creates account-level objects; all subsequent operations run as `OSS_SF_MLOPS_DEVELOPER`.
- Python 3.10 (driven by the Snowflake remote runtime).
- [`uv`](https://docs.astral.sh/uv/) package manager.

## Setup

1. Clone the repository.
2. Copy `.env.example` to `.env` and fill in Snowflake credentials. Set `SNOWFLAKE_ROLE=ACCOUNTADMIN` for the one-time hub bootstrap; switch to `SNOWFLAKE_ROLE=OSS_SF_MLOPS_DEVELOPER` for everything afterwards.

`uv` is invoked from each component's `Makefile` and syncs that component's lockfile on first use; no separate install step is required.

## End-to-end deploy

A fresh checkout reaches a fully deployed state by running these verbs in order. Each runs against the corresponding component; the root has no aggregator.

```sh
# 1. Hub: account-level resources + shared schemas (one-time, ACCOUNTADMIN).
make -C hub deploy-infra

# 2. Mock data: populate SHARED_DATA tables (OSS_SF_MLOPS_DEVELOPER).
make -C mock_data seed-shared-data

# 3. PUDO project: schema, feature store, training DAG, inference DAG.
make -C projects/pudo deploy-schema
make -C projects/pudo deploy-feature-store
make -C projects/pudo deploy-training-dag
make -C projects/pudo deploy-inference-dag
```

Each component's `Makefile` documents the full set of verbs available there (deploy, run, inference operations, lint, format). See the per-component `README.md` files.

## Where to read more

Full documentation at **[eraneos.github.io/snowflake-mlops](https://eraneos.github.io/snowflake-mlops/)**.

- `docs/start-here.md`: orientation and reading paths by role.
- `docs/index.md`: catalog of every documentation page.
- `docs/tutorials/`: step-by-step newcomer path (bootstrap, seed, deploy, train, infer).
- `docs/concepts/`: hub-spoke architecture, Snowflake ML lifecycle, feature store, model registry, task graphs, environment promotion.
- `docs/guides/`: practical how-tos (local setup, first end-to-end run, troubleshooting, Make targets).
- `docs/reference/`: command reference, component overview, glossary.
- `hub/README.md`, `mock_data/README.md`, `projects/pudo/README.md`, `feature_store/README.md`: per-component details.

## Contributing

Pull requests, criticism, and extensions are welcome. So are general Snowflake ML and MLOps questions that are not tied to a change here: if you are stuck getting Snowflake ML to work in your own setup, debugging a Tasks DAG, or sanity-checking an architecture decision, open an issue and we will have a look. See [CONTRIBUTING.md](CONTRIBUTING.md) for ways to engage and the Developer Certificate of Origin signoff requirement.

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
