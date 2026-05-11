# PUDO Capacity Prediction

## The business problem

**PUDO** stands for **Pick-Up / Drop-Off**: a network of locations where
customers collect or return parcels. Each PUDO location has a finite daily
capacity determined by its physical size, staffing, and operating hours.

The central operational question is:

> **How much capacity will each PUDO location need tomorrow?**

Underestimating capacity leads to overflow, missed deliveries, and customer
dissatisfaction. Overestimating wastes resources and increases cost.

## Why this is an ML problem

- Capacity demand depends on many factors: location type, nearby competing
  PUDOs, geographic density, day of week, seasonal patterns, and historical
  trends.
- Simple heuristics (e.g., last week's average) fail when conditions change.
- The relationship between features and demand is non-linear and benefits from
  gradient-boosted models.

## The data

The repository includes a **mock data generator** (`mock_data/`) that simulates
a realistic PUDO network:

| Data domain | Examples |
|---|---|
| PUDO locations | Geographic coordinates, location type, capacity, operating hours |
| Parcel volumes | Daily parcel counts, delivery attempts, occupancy rates |
| Temporal patterns | Day-of-week effects, seasonal trends, growth trajectories |
| Geospatial context | Nearby competing PUDOs, regional demand density |

The mock data is seeded into a shared Snowflake schema (`SHARED_DATA`) and
consumed by the feature store and downstream ML pipelines.

## Why this is a good MLOps reference

The PUDO problem exercises the full MLOps lifecycle:

1. **Feature engineering**: geospatial features, temporal aggregations,
   point-in-time correct feature views.
2. **Dataset generation**: spine construction, temporal train/val/test splits,
   ASOF joins for point-in-time correctness.
3. **Model training**: distributed XGBoost training via Snowflake Container
   Services, model evaluation, and registration in the Snowflake Model
   Registry.
4. **Batch inference**: automated feature generation, model loading, and
   prediction writing.
5. **Evaluation and monitoring**: prediction vs. actual comparison, alerting
   on threshold breaches, drift detection.
6. **Lifecycle management**: feature versioning, model versioning, environment
   promotion, and configuration overlays.

## Next step

Now that you understand the business problem, read the
[Repo Mental Model](./tutorials/02-repo-mental-model.md) to learn how the
codebase is organised, or start with
[Tutorial 1: Prerequisites & Bootstrap](./tutorials/01-prerequisites-and-snowflake-bootstrap.md)
if you are ready to set up your environment.
