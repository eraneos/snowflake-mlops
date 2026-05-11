# First End-to-End Run

A condensed checklist for running the full pipeline from scratch. Use this
after you have completed the [tutorials](../tutorials/index.md) and want a
quick reference.

## Prerequisites

- [x] Python 3.10 installed.
- [x] `uv` installed.
- [x] Snowflake account with `ACCOUNTADMIN` access.
- [x] Repository cloned.
- [x] `.env` files configured (see [Local Setup](local-setup-and-env-files.md)).

## Checklist

### 1. Bootstrap hub

```bash
make -C hub deploy-infra
```

### 2. Seed shared data

```bash
make -C mock_data seed-shared-data
```

### 3. Deploy PUDO project

```bash
make -C projects/pudo deploy-schema
make -C projects/pudo deploy-feature-store
```

### 4. Train a model

```bash
make -C projects/pudo deploy-training-dag
make -C projects/pudo run-training-dag
```

### 5. Run inference

```bash
make -C projects/pudo deploy-inference-dag
make -C projects/pudo run-inference-dag
```

### 6. Simulate a daily cycle

```bash
# Morning
make -C mock_data add-morning-data
make -C projects/pudo run-inference

# Evening
make -C mock_data add-evening-data
make -C projects/pudo evaluate-predictions
make -C projects/pudo inference-alerts
make -C projects/pudo inference-summary
```

### 7. Repeat or reset

```bash
# Check status
make -C mock_data simulation-status

# Reset if needed
make -C mock_data reset-simulation
```

## Common issues

If something fails, check [Troubleshooting](troubleshooting.md).
