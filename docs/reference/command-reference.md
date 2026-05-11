# Command Reference

All Makefile targets and CLI commands available in the repository.

## Hub

| Target | Command | Description |
|---|---|---|
| `deploy-infra` | `uv run python scripts/deploy_infra.py` | Bootstrap Snowflake platform infrastructure (databases, schemas, roles, warehouses, compute pools). |

```bash
make -C hub deploy-infra
```

## Mock Data

| Target | Command | Description |
|---|---|---|
| `seed-shared-data` | `uv run python scripts/seed_shared_data.py` | Generate and load initial PUDO data into `SHARED_DATA`. |
| `add-morning-data` | `uv run pudo-generate add-day morning` | Simulate morning parcel arrivals. |
| `add-evening-data` | `uv run pudo-generate add-day evening` | Simulate evening delivery completions. |
| `simulation-status` | `uv run pudo-generate simulation-status` | Display current simulation date and data counts. |
| `reset-simulation` | `uv run pudo-generate reset-simulation` | Reset the simulation clock to initial state. |

```bash
make -C mock_data seed-shared-data
make -C mock_data add-morning-data
make -C mock_data add-evening-data
make -C mock_data simulation-status
make -C mock_data reset-simulation
```

## PUDO Project: Deployment

| Target | Command | Description |
|---|---|---|
| `deploy-schema` | `uv run python scripts/deploy_schema.py` | Create the project schema in Snowflake. |
| `deploy-feature-store` | `uv run python scripts/deploy_feature_store.py` | Register entities and feature views in the Feature Store. |
| `deploy-training-dag` | `uv run python scripts/deploy_training_dag.py` | Deploy the training task graph. |
| `deploy-inference-dag` | `uv run python scripts/deploy_inference_dag.py` | Deploy the inference task graph. |

```bash
make -C projects/pudo deploy-schema
make -C projects/pudo deploy-feature-store
make -C projects/pudo deploy-training-dag
make -C projects/pudo deploy-inference-dag
```

## PUDO Project: Execution

| Target | Command | Description |
|---|---|---|
| `run-training-dag` | `uv run python scripts/run_training_dag.py` | Trigger the training task graph. |
| `run-inference-dag` | `uv run python scripts/run_inference_dag.py` | Trigger the inference task graph. |

```bash
make -C projects/pudo run-training-dag
make -C projects/pudo run-inference-dag
```

## PUDO Project: CLI Operations

| Target | Command | Description |
|---|---|---|
| `run-inference` | `uv run pudo-inference run` | Run batch inference via the CLI. |
| `evaluate-predictions` | `uv run pudo-inference evaluate` | Compare predictions to actuals and compute error metrics. |
| `inference-alerts` | `uv run pudo-inference alerts` | Check for alert conditions based on prediction error thresholds. |
| `inference-summary` | `uv run pudo-inference summary` | Print a summary of recent predictions and evaluation results. |

```bash
make -C projects/pudo run-inference
make -C projects/pudo evaluate-predictions
make -C projects/pudo inference-alerts
make -C projects/pudo inference-summary
```

## Typical execution order

### First-time setup

```bash
make -C hub deploy-infra
make -C mock_data seed-shared-data
make -C projects/pudo deploy-schema
make -C projects/pudo deploy-feature-store
make -C projects/pudo deploy-training-dag
make -C projects/pudo run-training-dag
make -C projects/pudo deploy-inference-dag
make -C projects/pudo run-inference-dag
```

### Daily cycle

```bash
make -C mock_data add-morning-data
make -C projects/pudo run-inference
make -C mock_data add-evening-data
make -C projects/pudo evaluate-predictions
make -C projects/pudo inference-alerts
make -C projects/pudo inference-summary
```
