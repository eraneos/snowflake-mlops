# Start Here

## What this repository is

This is an **open-source reference monorepo** that demonstrates how to build
production-grade MLOps on Snowflake. It uses a **hub-spoke architecture** where
a shared hub manages platform infrastructure and individual project spokes own
their own feature stores, training pipelines, and inference pipelines.

The reference project, **PUDO** (Pick-Up / Drop-Off), predicts parcel
capacity utilisation across a network of package drop-off and collection points.

## What this repository is not

- It is not a Snowflake SDK tutorial.
- It is not a general-purpose ML framework.
- It does not require a specific CI/CD platform to run locally.

## Prerequisites

Before starting the tutorials, you will need:

| Requirement | Why |
|---|---|
| A Snowflake account with `ACCOUNTADMIN` access (for initial bootstrap) | The hub component creates databases, warehouses, roles, and compute pools. |
| Python 3.10 | All components pin Python 3.10 for Snowflake runtime compatibility. |
| [uv](https://docs.astral.sh/uv/) | The package manager used across all components. |
| Git | For cloning the repository and for the environment-selection mechanism. |

## Two ways to use this documentation

### Guided path (recommended for newcomers)

Follow the tutorials in order:

1. [Prerequisites & Bootstrap](tutorials/01-prerequisites-and-snowflake-bootstrap.md)
2. [Repo Mental Model](tutorials/02-repo-mental-model.md)
3. [Seed Shared Data](tutorials/03-seed-shared-data.md)
4. [Deploy Schema & Feature Store](tutorials/04-deploy-schema-and-feature-store.md)
5. [Deploy & Run Training](tutorials/05-deploy-and-run-training.md)
6. [Deploy & Run Inference](tutorials/06-deploy-and-run-inference.md)
7. [Simulate, Evaluate & Alert](tutorials/07-simulate-morning-evening-and-evaluate.md)
8. [Change Promotion & ML Lifecycle](tutorials/08-change-promotion-and-ml-lifecycle.md)

### Concepts and reference (for experienced users)

If you already know Snowflake ML basics and want to understand the architecture
or look up a specific command:

- [Concepts](concepts/index.md): architecture, lifecycle, feature stores,
  orchestration, and environment promotion.
- [Guides](guides/index.md): practical how-to pages.
- [Reference](reference/index.md): command reference, component map, and
  glossary.

## Next step

Read the [PUDO Capacity Prediction use case](use-case.md)
to understand the business problem, then start with
[Tutorial 1: Prerequisites & Bootstrap](tutorials/01-prerequisites-and-snowflake-bootstrap.md).
