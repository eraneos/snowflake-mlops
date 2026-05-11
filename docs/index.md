# Snowflake MLOps Reference

<div class="eraneos-hero" markdown>

**An [Eraneos](https://www.eraneos.com/){:target="_blank"} reference monorepo** showing what end-to-end MLOps on Snowflake can look like, and how a broad range of Snowflake-native MLOps primitives fit together in one coherent example.

</div>

## Why this repo exists

Existing Snowflake ML material covers individual pieces of the workflow. This repo wires those pieces into a single worked example for a realistic, multi-team setup.

It does two things at once:

- **Demonstrates end-to-end MLOps on Snowflake in a multi-team layout.** The reference uses a hub-spoke architecture: a central platform hub owns infrastructure and governance; project spokes own their feature views, training pipelines, and inference pipelines. Hub-spoke is one specific way to organize the example; the patterns generalize.
- **Showcases the breadth of Snowflake-native MLOps features and how they interact.** Feature engineering with the [Snowflake Feature Store](concepts/feature-store.md), model lifecycle in the [Snowflake ML Model Registry](concepts/model-registry-and-training-artifacts.md), training and batch inference orchestrated through [Snowflake Tasks DAGs](concepts/task-graphs-and-orchestration.md), native observability via `TASK_HISTORY` and Account Usage, and the supporting primitives (databases, schemas, warehouses, compute pools, roles, stages) that wire them together. Snowflake-native primitives are preferred over external tooling wherever the native option is viable.

Everything is showcased through a single end-to-end example, drawn from a logistics and parcel-delivery context: predicting capacity utilisation at **Pick-Up / Drop-Off points (PUDO)**, the network of shops, lockers, and service points where parcels are dropped off and collected. All data for the example is synthetic and generated locally (see the `mock_data/` component), so the repo runs end-to-end on a fresh checkout without any real upstream data source. See the [use case](use-case.md) for the business framing.

## What you will find here

<div class="eraneos-cards" markdown>

<div class="eraneos-card" markdown>
### [Use Case](use-case.md)
The PUDO (Pick-Up / Drop-Off) capacity prediction business problem that drives the reference implementation.
</div>

<div class="eraneos-card" markdown>
### [Tutorials](tutorials/index.md)
Step-by-step newcomer path: bootstrap Snowflake, seed data, deploy feature stores, train a model, run inference, simulate daily cycles, and evaluate results.
</div>

<div class="eraneos-card" markdown>
### [Concepts](concepts/index.md)
Hub-spoke architecture, Snowflake ML lifecycle stages, feature stores, model registries, task-graph orchestration, and environment promotion.
</div>

<div class="eraneos-card" markdown>
### [Guides](guides/index.md)
Practical how-to pages for local setup, first end-to-end runs, troubleshooting, and working with component Makefiles.
</div>

<div class="eraneos-card" markdown>
### [Reference](reference/index.md)
Concise command reference, component map, and glossary.
</div>

</div>

## Who this is for

- **Platform and ML engineers** evaluating Snowflake as an MLOps platform.
- **Data scientists** who want to understand how models move from notebooks to
  production task graphs.
- **Engineering leads** designing multi-project ML architectures on Snowflake.

## Quick start

If you already have a Snowflake account and the basic tooling installed, jump
straight to the [first tutorial](tutorials/01-prerequisites-and-snowflake-bootstrap.md).

If you are new to the repository, start with [Start Here](start-here.md).
