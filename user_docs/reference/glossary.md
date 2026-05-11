# Glossary

Definitions of key terms used throughout this documentation.

## Repository terms

| Term | Definition |
|---|---|
| **Hub** | The central component that creates and manages shared Snowflake platform infrastructure (databases, schemas, roles, warehouses). |
| **Spoke** | A project component that owns its own ML pipeline (feature views, training, inference). |
| **Component** | A self-contained directory with its own `pyproject.toml`, `Makefile`, and `.env`. |
| **PUDO** | Pick-Up / Drop-Off, a location where customers collect or return parcels. The reference use case in this repository. |

## Snowflake ML terms

| Term | Definition |
|---|---|
| **Feature Store** | A Snowflake-native registry for ML features, providing versioning, point-in-time correctness, and discoverability. |
| **Feature View** | A versioned collection of computed features, managed by the Feature Store. |
| **Entity** | A primary key definition that features are organised around (e.g., `PUDO_ID`). |
| **Model Registry** | A Snowflake-native store for ML models with versioning, metrics, and lineage. |
| **Task Graph (DAG)** | A Snowflake-native orchestration mechanism for defining and executing multi-step pipelines. |
| **Snowpark** | Snowflake's Python API for building data processing and ML applications that run in Snowflake. |
| **Container Services** | Snowflake's container runtime for running distributed compute workloads (e.g., XGBoost training). |
| **Compute Pool** | A pool of compute resources (CPU/GPU) for Container Services. |
| **ASOF JOIN** | A join that matches each row to the most recent preceding row by timestamp. Used for point-in-time feature lookups. |
| **Point-in-time correctness** | Ensuring that feature values used for training or inference were actually available at the time of prediction, preventing data leakage. |

## MLOps terms

| Term | Definition |
|---|---|
| **Data leakage** | Using future information during model training, leading to overly optimistic performance estimates. |
| **Training-serving skew** | A mismatch between how features are computed during training vs. inference. |
| **Data drift** | A change in the input data distribution over time. |
| **Concept drift** | A change in the relationship between features and the target variable over time. |
| **Spine** | A list of (entity, timestamp) pairs that define the prediction context for dataset generation. |
| **Temporal split** | Splitting data by time rather than randomly, preserving temporal ordering to prevent leakage. |
| **Batch inference** | Running predictions on a batch of inputs, as opposed to real-time inference on individual requests. |
| **Model lineage** | The traceable connection between a model and the data, features, and configuration that produced it. |
| **Configuration overlay** | Environment-specific YAML overrides merged with base configuration, similar to Kustomize. |
| **Deploy-vs-run** | The pattern of first deploying a pipeline definition (DAG) and then separately triggering its execution. |

## Acronyms

| Acronym | Full term |
|---|---|
| DAG | Directed Acyclic Graph |
| ML | Machine Learning |
| MLOps | Machine Learning Operations |
| PUDO | Pick-Up / Drop-Off |
| RMSE | Root Mean Square Error |
| MAE | Mean Absolute Error |
| CI/CD | Continuous Integration / Continuous Deployment |
