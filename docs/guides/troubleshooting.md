# Troubleshooting

Common issues and how to resolve them.

## Connection errors

### "Cannot create session" or "Role does not exist"

**Cause:** The `.env` file is missing or the role has not been created yet.

**Fix:**

1. Verify the `.env` file exists in the component directory.
2. If this is the first run, use `ACCOUNTADMIN` for the hub bootstrap.
3. After bootstrap, switch to the operational role created by the hub.

```bash
# Check your .env
cat hub/.env

# Verify the role exists in Snowflake
snow sql -q "SHOW ROLES LIKE 'PUDO%'"
```

### "Database does not exist"

**Cause:** Hub infrastructure has not been deployed yet.

**Fix:**

```bash
make -C hub deploy-infra
```

## Training errors

### Training DAG fails to deploy

**Cause:** The compute pool or warehouse does not exist.

**Fix:**

1. Verify hub bootstrap completed successfully.
2. Check that the compute pool exists:

```sql
SHOW COMPUTE POOLS LIKE 'PUDO%';
```

3. Check that the warehouse exists:

```sql
SHOW WAREHOUSES LIKE 'PUDO%';
```

### Training job fails with "libomp not found" (macOS)

**Cause:** XGBoost requires `libomp` which may not be installed on macOS.

**Fix:**

```bash
brew install libomp
```

### Training takes too long in DEV

**Cause:** DEV configuration may still use production-scale parameters.

**Fix:** Check `config/training/dev.override.yaml` and reduce parameters:

```yaml
train_days: 30
n_estimators: 50
```

## Inference errors

### "No model found in registry"

**Cause:** Training has not completed or the model was registered under a
different name.

**Fix:**

1. Verify training completed successfully:

```bash
make -C projects/pudo run-training-dag
```

2. Check the model registry:

```sql
SELECT * FROM PUDO_DEV.MODEL_REGISTRY.MODELS;
```

### Inference produces no predictions

**Cause:** No data is available for the target date.

**Fix:**

1. Check that shared data has been seeded:

```bash
make -C mock_data simulation-status
```

2. If the simulation has not advanced far enough, add data:

```bash
make -C mock_data add-morning-data
```

## Mock data errors

### "Simulation has not been initialised"

**Cause:** The shared data has not been seeded yet.

**Fix:**

```bash
make -C mock_data seed-shared-data
```

### Simulation clock is stuck

**Cause:** You may have already reached the simulation end date.

**Fix:**

1. Check simulation status:

```bash
make -C mock_data simulation-status
```

2. Reset if needed:

```bash
make -C mock_data reset-simulation
make -C mock_data seed-shared-data
```

## General debugging tips

### Check the environment

```bash
# Which Git branch am I on? (determines the Snowflake environment)
git branch --show-current

# Which Python version?
python --version   # Should be 3.10.x

# Is uv installed?
uv --version
```

### Check Snowflake state

```sql
-- What databases exist?
SHOW DATABASES LIKE 'PUDO%';

-- What schemas exist?
SHOW SCHEMAS IN DATABASE PUDO_MLOPS;

-- What tasks exist?
SHOW TASKS IN SCHEMA PUDO_DEV;

-- Recent task history
SELECT * FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY())
  ORDER BY SCHEDULED_TIME DESC LIMIT 20;
```

### Enable verbose logging

Most scripts accept environment variables for debugging:

```bash
# Enable Snowflake connector logging
export SNOWFLAKE_LOG_LEVEL=DEBUG
make -C projects/pudo deploy-schema
```
