# Tutorial 5: Deploy & Run Training

This tutorial deploys the training task graph and runs the full training
pipeline: dataset generation, distributed XGBoost training, model evaluation,
and model registration.

## What you will learn

- How the training DAG is structured.
- How datasets are generated from the feature store with point-in-time
  correctness.
- How distributed XGBoost training works in Snowflake Container Services.
- How models are registered in the Snowflake Model Registry.

## Before you start

- [x] Feature store is deployed ([Tutorial 4](04-deploy-schema-and-feature-store.md)).

## Step 1: Deploy the training DAG

```bash
make -C projects/pudo deploy-training-dag
```

This creates a Snowflake **task graph** (DAG) that orchestrates the training
pipeline. The DAG consists of tasks that:

1. **Generate dataset**: constructs a spine, performs ASOF joins against
   feature views for point-in-time correctness, and splits into train/val/test.
2. **Train model**: runs distributed XGBoost training via Snowflake Container
   Services.
3. **Evaluate model**: computes metrics (RMSE, MAE) on the validation set.
4. **Register model**: logs the model with metrics in the Snowflake Model
   Registry.

## Step 2: Run the training DAG

```bash
make -C projects/pudo run-training-dag
```

This triggers an immediate execution of the training task graph. You can
monitor progress in Snowflake:

```sql
-- Check task graph status
SELECT * FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY())
  WHERE NAME LIKE 'TRAINING%'
  ORDER BY SCHEDULED_TIME DESC;

-- Check the model registry
SELECT * FROM PUDO_DEV.MODEL_REGISTRY.MODELS;
```

## How dataset generation works

The training pipeline generates datasets using a **spine**: a list of
(entity, timestamp) pairs that define the prediction context:

1. **Spine construction**: for each (PUDO, date) pair, create a row
   representing "predict capacity for this PUDO on this date."
2. **ASOF JOIN**: for each spine row, look up the feature values that were
   available at that point in time. This prevents data leakage.
3. **Temporal split**: split the dataset into train, validation, and test
   sets based on time (not random), preserving temporal ordering.

## How distributed training works

The training task uses **Snowflake Container Services** to run distributed
XGBoost training:

- A compute pool (created during hub bootstrap) provides the compute resources.
- The training job runs in a container with the XGBoost library pre-installed.
- Data is read directly from Snowflake stages. No data movement outside the
   platform.
- Training metrics (RMSE, MAE, R²) are logged to the Model Registry.

## Configuration

Training behaviour is controlled by YAML configuration:

```
projects/pudo/config/training/
├── base.yaml              # Default training parameters
├── dev.override.yaml      # Dev overrides (fewer estimators, smaller data)
├── staging.override.yaml  # Staging overrides
└── prod.override.yaml     # Production overrides
```

Typical configurable parameters:

| Parameter | What it controls |
|---|---|
| `train_days` | Number of historical days to include in training. |
| `n_estimators` | Number of XGBoost boosting rounds. |
| `learning_rate` | XGBoost learning rate. |
| `max_depth` | Maximum tree depth. |
| `compute_pool` | Snowflake compute pool for container training. |

## Step 3: Verify the trained model

After the DAG completes, verify the model in the registry:

```sql
-- List models
SELECT name, version, created_on
FROM PUDO_DEV.MODEL_REGISTRY.MODELS;

-- View model metrics
SELECT name, version, metrics
FROM PUDO_DEV.MODEL_REGISTRY.MODEL_VERSIONS;
```

## What you have now

- [x] Training DAG deployed and executed.
- [x] Dataset generated with point-in-time correctness.
- [x] XGBoost model trained and evaluated.
- [x] Model registered in the Snowflake Model Registry with metrics.

## Next step

Continue to [Tutorial 6: Deploy & Run Inference](06-deploy-and-run-inference.md)
to deploy the inference pipeline and generate batch predictions.
