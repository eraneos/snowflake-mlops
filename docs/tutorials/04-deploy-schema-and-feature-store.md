# Tutorial 4: Deploy Schema & Feature Store

This tutorial creates the PUDO project schema in Snowflake and registers the
feature store entities and feature views.

## What you will learn

- How to deploy a project-specific schema.
- How entities and feature views are defined and registered.
- How the feature store connects to the shared data.

## Before you start

- [x] Hub infrastructure is deployed.
- [x] Shared data is seeded ([Tutorial 3](03-seed-shared-data.md)).

## Step 1: Deploy the project schema

```bash
make -C projects/pudo deploy-schema
```

This creates the project-specific schema (`PUDO_DEV` or equivalent depending
on your environment) in Snowflake. The schema holds:

- Project-specific tables (inference outputs, evaluation results).
- Feature store objects.
- Model registry objects.

## Step 2: Deploy the feature store

```bash
make -C projects/pudo deploy-feature-store
```

This registers:

1. **Entities**: the primary keys that features are organised around:
   - `PUDO` entity, keyed by PUDO location ID.
   - `PUDO_DATE` entity, composite key of PUDO ID and date (for temporal
     features).

2. **Feature views**: collections of related features computed from the shared
   data:

   | Feature view | Features |
   |---|---|
   | `pudo_geospatial_features` | Number of nearby competing PUDOs, total nearby capacity. |
   | `pudo_historical_features` | Historical parcel volumes, delivery success rates. |
   | `pudo_temporal_features` | Daily parcel demand, day-of-week patterns. |

## How feature views work

Each feature view is a Snowflake-managed view that:

1. Reads from the `SHARED_DATA` tables.
2. Computes features using SQL or Snowpark transformations.
3. Registers the results in the Feature Store with point-in-time correctness.

The feature views are versioned. When you deploy, a new version is created if
the feature definitions have changed. Downstream consumers (training,
inference) reference specific versions through configuration.

## Configuration

Feature store behaviour is controlled by YAML configuration in
`projects/pudo/config/`:

```
config/
├── feature_view/
│   ├── feature_store/
│   │   ├── base.yaml
│   │   └── dev.override.yaml
│   └── feature_views/
│       ├── base.yaml
│       └── dev.override.yaml
```

The `feature_store/` configures the Feature Store instance (database, schema,
versioning). The `feature_views/` configures individual feature view parameters
(lookback windows, aggregation levels, version pins).

## Step 3: Verify the feature store

You can verify the feature store deployment by querying Snowflake:

```sql
-- List registered entities
SELECT * FROM PUDO_DEV.FEATURE_STORE.ENTITIES;

-- List feature views and their versions
SELECT * FROM PUDO_DEV.FEATURE_STORE.FEATURE_VIEWS;
```

## What you have now

- [x] Project schema created in Snowflake.
- [x] Entities registered (PUDO, PUDO_DATE).
- [x] Feature views deployed (geospatial, historical, temporal).
- [x] Feature store ready for dataset generation.

## Next step

Continue to [Tutorial 5: Deploy & Run Training](05-deploy-and-run-training.md)
to train your first model using the feature store data.
