# Tutorial 3: Seed Shared Data

This tutorial loads the initial mock PUDO data into the shared Snowflake schema.

## What you will learn

- How to seed the `SHARED_DATA` schema with realistic PUDO data.
- How to inspect the seeded data.
- How the mock data generator works.

## Before you start

- [x] Hub infrastructure is deployed ([Tutorial 1](01-prerequisites-and-snowflake-bootstrap.md)).
- [x] You understand the repo layout ([Tutorial 2](02-repo-mental-model.md)).

## Step 1: Seed the shared data

From the repository root:

```bash
make -C mock_data seed-shared-data
```

This runs `uv run python scripts/seed_shared_data.py`, which:

1. Connects to Snowflake using the credentials in `mock_data/.env`.
2. Creates the PUDO tables in `SHARED_DATA` if they do not exist.
3. Generates a realistic PUDO network with locations, parcels, delivery
   attempts, and occupancy records.
4. Loads the generated data into Snowflake.

## Step 2: Verify the data

You can verify the seeded data by running queries in Snowflake:

```sql
USE SCHEMA SHARED_DATA.PUBLIC;

SELECT COUNT(*) AS pudo_count FROM PUDO_LOCATIONS;
SELECT COUNT(*) AS parcel_count FROM PARCELS;
SELECT COUNT(*) AS delivery_count FROM DELIVERY_ATTEMPTS;
SELECT COUNT(*) AS occupancy_count FROM OCCUPANCY;
```

## Step 3: Check simulation status

The mock data generator tracks a simulation clock. You can check the current
state:

```bash
make -C mock_data simulation-status
```

This shows the current simulation date and how many days of data have been
generated.

## What the mock data contains

| Table | Content |
|---|---|
| `PUDO_LOCATIONS` | PUDO sites with coordinates, type, capacity, and operating hours. |
| `PARCELS` | Individual parcel records with origin, destination, and timestamps. |
| `DELIVERY_ATTEMPTS` | Delivery attempts with success/failure outcomes. |
| `OCCUPANCY` | Hourly occupancy readings per PUDO location. |

## Incremental data generation

After the initial seed, you can add data incrementally to simulate daily
operations:

```bash
# Simulate morning arrivals
make -C mock_data add-morning-data

# Simulate evening completions
make -C mock_data add-evening-data
```

These commands advance the simulation clock and add a new day's worth of data.
You will use them in [Tutorial 7](07-simulate-morning-evening-and-evaluate.md)
to create evaluation cycles.

## Resetting the simulation

If you need to start over:

```bash
make -C mock_data reset-simulation
```

This resets the simulation clock to the initial state. You will need to
re-seed the data.

## What you have now

- [x] `SHARED_DATA` schema populated with mock PUDO data.
- [x] Understanding of the simulation lifecycle.

## Next step

Continue to [Tutorial 4: Deploy Schema & Feature Store](04-deploy-schema-and-feature-store.md)
to create the project-specific schema and register feature views.
