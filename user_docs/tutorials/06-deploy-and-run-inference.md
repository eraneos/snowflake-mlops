# Tutorial 6: Deploy & Run Inference

This tutorial deploys the inference task graph and runs batch predictions using
the trained model.

## What you will learn

- How the inference DAG is structured.
- How batch inference loads features and generates predictions.
- Where predictions are stored and how to inspect them.

## Before you start

- [x] Training is complete and a model is registered
  ([Tutorial 5](05-deploy-and-run-training.md)).

## Step 1: Deploy the inference DAG

```bash
make -C projects/pudo deploy-inference-dag
```

This creates a Snowflake task graph that orchestrates the inference pipeline:

1. **Load model**: retrieves the latest (or configured) model version from the
  Model Registry.
2. **Generate features**: computes inference-time features from the feature
   store for the target date.
3. **Run predictions**: applies the model to the feature matrix.
4. **Write results**: stores predictions in the project schema.

## Step 2: Run the inference DAG

```bash
make -C projects/pudo run-inference-dag
```

This triggers an immediate execution of the inference task graph.

### Alternative: CLI-based inference

You can also run inference directly without the DAG:

```bash
make -C projects/pudo run-inference
```

This runs `pudo-inference run`, which performs the same steps as the DAG but
from your local terminal. This is useful for debugging or ad-hoc runs.

## How inference works

The inference pipeline:

1. Reads the model version from configuration (or uses the latest).
2. Constructs an inference spine, one row per (PUDO, target_date).
3. Performs ASOF JOINs against feature views to get point-in-time features.
4. Applies the trained XGBoost model to generate predictions.
5. Writes predictions with metadata (model version, run timestamp, features
   used) to the project schema.

## Step 3: Inspect predictions

```sql
-- View recent predictions
SELECT *
FROM PUDO_DEV.PREDICTIONS
ORDER BY PREDICTION_DATE DESC
LIMIT 20;

-- Check prediction distribution
SELECT
  PREDICTION_DATE,
  COUNT(*) AS num_predictions,
  AVG(PREDICTED_CAPACITY) AS avg_predicted,
  STDDEV(PREDICTED_CAPACITY) AS std_predicted
FROM PUDO_DEV.PREDICTIONS
GROUP BY PREDICTION_DATE
ORDER BY PREDICTION_DATE DESC;
```

## Inference CLI verbs

The `pudo-inference` CLI provides additional verbs for post-inference
operations:

| Command | What it does |
|---|---|
| `pudo-inference run` | Run batch inference. |
| `pudo-inference evaluate` | Compare predictions to actuals and compute metrics. |
| `pudo-inference alerts` | Check for alert conditions (e.g., high prediction error). |
| `pudo-inference summary` | Print a summary of recent predictions. |

You will use `evaluate`, `alerts`, and `summary` in
[Tutorial 7](07-simulate-morning-evening-and-evaluate.md).

## What you have now

- [x] Inference DAG deployed and executed.
- [x] Batch predictions generated and stored in Snowflake.
- [x] Understanding of the inference CLI verbs.

## Next step

Continue to [Tutorial 7: Simulate, Evaluate & Alert](07-simulate-morning-evening-and-evaluate.md)
to simulate daily data cycles, evaluate prediction quality, and trigger alerts.
