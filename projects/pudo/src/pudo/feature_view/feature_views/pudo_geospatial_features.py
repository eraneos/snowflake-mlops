from snowflake.ml.feature_store import FeatureView
from snowflake.snowpark.functions import call_function, coalesce, col, count, date_trunc, lit, sum as sum_, when
from snowflake.snowpark.types import DoubleType, IntegerType

from pudo.core.config.infrastructure import config as infra_config
from pudo.core.registry import register_feature_view

# -----------------------------
# Feature Functions
# -----------------------------


def num_nearby_competing_pudos(session, pudo_reference_df):
    """
    Feature: Number of competing PUDOs within 1 km radius.
    """
    competitor_pudo_df = pudo_reference_df.select(
        col("PUDO_ID").alias("COMPETING_PUDO_ID"),
        col("LATITUDE").alias("COMPETING_LATITUDE"),
        col("LONGITUDE").alias("COMPETING_LONGITUDE"),
    )

    return (
        pudo_reference_df.cross_join(competitor_pudo_df)
        .select(
            col("PUDO_ID"),
            col("COMPETING_PUDO_ID"),
            call_function(
                "ST_DISTANCE",
                call_function("ST_POINT", col("LONGITUDE"), col("LATITUDE")),
                call_function("ST_POINT", col("COMPETING_LONGITUDE"), col("COMPETING_LATITUDE")),
            ).alias("DISTANCE_METERS"),
        )
        .filter(col("PUDO_ID") != col("COMPETING_PUDO_ID"))
        .group_by("PUDO_ID")
        .agg(
            coalesce(count(when(col("DISTANCE_METERS") <= lit(1000), lit(1))), lit(0))
            .cast(IntegerType())
            .alias("NUM_NEARBY_COMPETING_PUDOS")
        )
    )


def total_nearby_pudo_capacity(session, pudo_reference_df):
    """
    Feature: Total capacity of competing PUDOs within 1 km radius.
    """
    competitor_pudo_df = pudo_reference_df.select(
        col("PUDO_ID").alias("COMPETING_PUDO_ID"),
        col("LATITUDE").alias("COMPETING_LATITUDE"),
        col("LONGITUDE").alias("COMPETING_LONGITUDE"),
        col("CAPACITY").alias("COMPETING_CAPACITY"),
    )

    return (
        pudo_reference_df.cross_join(competitor_pudo_df)
        .select(
            col("PUDO_ID"),
            col("COMPETING_PUDO_ID"),
            col("COMPETING_CAPACITY"),
            call_function(
                "ST_DISTANCE",
                call_function("ST_POINT", col("LONGITUDE"), col("LATITUDE")),
                call_function("ST_POINT", col("COMPETING_LONGITUDE"), col("COMPETING_LATITUDE")),
            ).alias("DISTANCE_METERS"),
        )
        .filter(col("PUDO_ID") != col("COMPETING_PUDO_ID"))
        .group_by("PUDO_ID")
        .agg(
            coalesce(
                sum_(when(col("DISTANCE_METERS") <= lit(1000), col("COMPETING_CAPACITY")).otherwise(lit(0))), lit(0)
            )
            .cast(IntegerType())
            .alias("TOTAL_NEARBY_PUDO_CAPACITY")
        )
    )


def daily_parcel_demand(session, pudo_reference_df):
    """
    Feature: Daily parcel demand assigned to the closest PUDO using ST_WITHIN for efficiency.
    """
    # Get database and schema from infrastructure config
    parcels_with_date_df = session.table(
        f"{infra_config.database.name}.{infra_config.shared_data.schema_name}.PARCELS"
    ).select(
        date_trunc("day", col("CREATED_DATE")).alias("PARCEL_DATE"),
        col("DESTINATION_LAT").alias("DEST_LAT"),
        col("DESTINATION_LON").alias("DEST_LON"),
        col("PARCEL_DATE").alias("PARCEL_DATE_P"),
        call_function("ST_POINT", col("DEST_LON"), col("DEST_LAT")).alias("PARCEL_POINT"),
    )

    pudo_copy_df = pudo_reference_df.select(
        col("PUDO_ID").alias("PUDO_ID_P"),
        call_function("ST_POINT", col("LONGITUDE"), col("LATITUDE")).alias("PUDO_POINT"),
    )

    # Use ST_DWITHIN to check if parcel is within 1 km of PUDO
    parcel_pudo_within_df = (
        parcels_with_date_df.cross_join(pudo_copy_df)
        .filter(call_function("ST_DWITHIN", col("PARCEL_POINT"), col("PUDO_POINT"), lit(1000)))
        .select(col("PARCEL_DATE_P").alias("PARCEL_DATE"), col("PUDO_ID_P").alias("PUDO_ID"))
    )

    return parcel_pudo_within_df.group_by("PARCEL_DATE", "PUDO_ID").agg(count(lit(1)).alias("DAILY_PARCEL_DEMAND"))


def demand_capacity_ratio(competing_df, parcel_df):
    """
    Feature: Ratio of parcel demand to nearby PUDO capacity.
    """
    return competing_df.join(parcel_df, on="PUDO_ID", how="right").select(
        col("PUDO_ID"),
        col("PARCEL_DATE").alias("DATE"),
        col("PARCEL_DATE").alias("UPDATED_AT"),
        coalesce(col("NUM_NEARBY_COMPETING_PUDOS"), lit(0)).alias("NUM_NEARBY_COMPETING_PUDOS"),
        coalesce(col("TOTAL_NEARBY_PUDO_CAPACITY"), lit(0)).alias("TOTAL_NEARBY_PUDO_CAPACITY"),
        coalesce(col("DAILY_PARCEL_DEMAND"), lit(0)).alias("DAILY_PARCEL_DEMAND"),
        (col("DAILY_PARCEL_DEMAND") / (col("TOTAL_NEARBY_PUDO_CAPACITY").cast(DoubleType()) + lit(1e-9))).alias(
            "DEMAND_CAPACITY_RATIO"
        ),
    )


# -----------------------------
# Main Feature View Function
# -----------------------------


@register_feature_view("pudo__geospatial_features")
def create_pudo_geospatial_features(session, entities, refresh_freq=None, warehouse=None):
    """
    Compute geospatial features for PUDO (Pick-Up Drop-Off) points, including:
    - NUM_NEARBY_COMPETING_PUDOS
    - TOTAL_NEARBY_PUDO_CAPACITY
    - DAILY_PARCEL_DEMAND
    - DEMAND_CAPACITY_RATIO
    """
    # Load reference data
    pudo_table = f"{infra_config.database.name}.{infra_config.shared_data.schema_name}.PUDO_REFERENCE"

    pudo_reference_df = session.table(pudo_table).select(
        col("PUDO_ID"), col("LATITUDE"), col("LONGITUDE"), col("CAPACITY"), col("PUDO_TYPE")
    )

    competing_pudos_df = num_nearby_competing_pudos(session, pudo_reference_df).join(
        total_nearby_pudo_capacity(session, pudo_reference_df), on="PUDO_ID", how="outer"
    )

    parcel_demand_df = daily_parcel_demand(session, pudo_reference_df)

    final_features_df = demand_capacity_ratio(competing_pudos_df, parcel_demand_df)

    feature_view_kwargs = {
        "name": "PUDO__GEOSPATIAL_FEATURES",
        "entities": [entities["PUDO"]],
        "feature_df": final_features_df,
        "timestamp_col": "UPDATED_AT",
        "desc": "Geospatial features for PUDO points with competition, capacity, and demand metrics.",
    }

    # Add refresh configuration. Warehouse is only set when a schedule is configured
    # to prevent AUTO refresh without a schedule.
    if refresh_freq is not None:
        feature_view_kwargs["refresh_freq"] = refresh_freq
    if warehouse:
        feature_view_kwargs["warehouse"] = warehouse

    return FeatureView(**feature_view_kwargs)
