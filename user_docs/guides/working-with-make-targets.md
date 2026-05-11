# Working with Make Targets

This guide explains the Makefile structure and how to use the available
targets across components.

## The Makefile pattern

Each component has its own `Makefile` with operational targets. There is no
root `Makefile`. You always run commands from within a component directory
or use `make -C <component>` from the repository root.

## Running targets

```bash
# From the repository root
make -C hub deploy-infra
make -C mock_data seed-shared-data
make -C projects/pudo deploy-schema

# Or from within the component directory
cd projects/pudo
make deploy-schema
```

## Hub targets

| Target | Command | Description |
|---|---|---|
| `deploy-infra` | `uv run python scripts/deploy_infra.py` | Bootstrap all Snowflake platform infrastructure. |

## Mock data targets

| Target | Command | Description |
|---|---|---|
| `seed-shared-data` | `uv run python scripts/seed_shared_data.py` | Initial bulk load of PUDO data. |
| `add-morning-data` | `uv run pudo-generate add-day morning` | Simulate morning arrivals. |
| `add-evening-data` | `uv run pudo-generate add-day evening` | Simulate evening completions. |
| `simulation-status` | `uv run pudo-generate simulation-status` | Show simulation state. |
| `reset-simulation` | `uv run pudo-generate reset-simulation` | Reset simulation clock. |

## PUDO project targets

### Deployment targets

| Target | Command | Description |
|---|---|---|
| `deploy-schema` | `uv run python scripts/deploy_schema.py` | Create project schema. |
| `deploy-feature-store` | `uv run python scripts/deploy_feature_store.py` | Register entities and feature views. |
| `deploy-training-dag` | `uv run python scripts/deploy_training_dag.py` | Deploy training task graph. |
| `deploy-inference-dag` | `uv run python scripts/deploy_inference_dag.py` | Deploy inference task graph. |

### Execution targets

| Target | Command | Description |
|---|---|---|
| `run-training-dag` | `uv run python scripts/run_training_dag.py` | Execute training pipeline. |
| `run-inference-dag` | `uv run python scripts/run_inference_dag.py` | Execute inference pipeline. |

### CLI targets

| Target | Command | Description |
|---|---|---|
| `run-inference` | `uv run pudo-inference run` | Run batch inference via CLI. |
| `evaluate-predictions` | `uv run pudo-inference evaluate` | Evaluate predictions vs actuals. |
| `inference-alerts` | `uv run pudo-inference alerts` | Check alert conditions. |
| `inference-summary` | `uv run pudo-inference summary` | Print prediction summary. |

## Common patterns

### First-time setup

```bash
make -C hub deploy-infra
make -C mock_data seed-shared-data
make -C projects/pudo deploy-schema
make -C projects/pudo deploy-feature-store
```

### Training cycle

```bash
make -C projects/pudo deploy-training-dag
make -C projects/pudo run-training-dag
```

### Inference cycle

```bash
make -C projects/pudo deploy-inference-dag
make -C projects/pudo run-inference-dag
```

### Daily simulation cycle

```bash
make -C mock_data add-morning-data
make -C projects/pudo run-inference
make -C mock_data add-evening-data
make -C projects/pudo evaluate-predictions
make -C projects/pudo inference-alerts
make -C projects/pudo inference-summary
```

## Adding new targets

To add a new target to a component's Makefile:

```makefile
.PHONY: new-target

new-target:
	uv run python scripts/new_script.py
```

Follow the existing pattern:

- Use `.PHONY` for all targets.
- Use `uv run` to execute scripts (handles the virtual environment).
- Keep targets atomic. Each target does one thing.
