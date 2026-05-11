# Tutorials

A step-by-step guided path from zero to a running MLOps pipeline on Snowflake.

Follow the tutorials in order the first time through. Each tutorial assumes you
have completed the previous one.

| # | Tutorial | What you will do |
|---|---|---|
| 1 | [Prerequisites & Bootstrap](01-prerequisites-and-snowflake-bootstrap.md) | Install tooling, configure Snowflake access, bootstrap platform infrastructure. |
| 2 | [Repo Mental Model](02-repo-mental-model.md) | Understand the hub-spoke layout, component boundaries, and how code is organised. |
| 3 | [Seed Shared Data](03-seed-shared-data.md) | Generate and load mock PUDO data into the shared Snowflake schema. |
| 4 | [Deploy Schema & Feature Store](04-deploy-schema-and-feature-store.md) | Create the project schema, entities, and feature views. |
| 5 | [Deploy & Run Training](05-deploy-and-run-training.md) | Deploy the training DAG, generate datasets, train an XGBoost model, and register it. |
| 6 | [Deploy & Run Inference](06-deploy-and-run-inference.md) | Deploy the inference DAG and run batch predictions. |
| 7 | [Simulate, Evaluate & Alert](07-simulate-morning-evening-and-evaluate.md) | Simulate daily data cycles, evaluate predictions, and trigger alerts. |
| 8 | [Change Promotion & ML Lifecycle](08-change-promotion-and-ml-lifecycle.md) | Understand how Git changes map to Snowflake ML lifecycle stages. |

## Before you start

Make sure you have read:

- [Start Here](../start-here.md) for prerequisites and audience.
- [PUDO Capacity Prediction](../use-case.md) for the business context.
