from snowflake.ml.feature_store import FeatureView
from snowflake.snowpark.functions import (
    avg,
    col,
    dayofmonth,
    dayofweek,
    last_day,
    lit,
    month,
    quarter,
    stddev,
    when,
)

from pudo.core.config.data_generation import config as data_gen_config
from pudo.core.config.infrastructure import config as infra_config
from pudo.core.registry import register_feature_view


@register_feature_view("pudo__temporal_features")
def create_pudo_temporal_features(session, entities, refresh_freq, warehouse=None):
    """Create temporal and seasonal features using Snowpark DataFrames."""
    # Load base occupancy data
    occupancy_table = f"{infra_config.database.name}.{infra_config.shared_data.schema_name}.PUDO_OCCUPANCY"
    occupancy_df = session.table(occupancy_table)

    # Get start date from data generation config
    start_date = data_gen_config.start_date

    # Create temporal base features
    temporal_base_df = occupancy_df.select(
        col("PUDO_ID"),
        col("DATE"),
        col("DATE").alias("UPDATED_AT"),  # Timestamp column for data freshness
        col("FILL_RATE"),  # Keep temporarily for seasonal pattern calculation
        col("DAILY_DELIVERIES"),
        # Extract temporal components
        dayofweek(col("DATE")).alias("DAY_OF_WEEK"),
        dayofmonth(col("DATE")).alias("DAY_OF_MONTH"),
        month(col("DATE")).alias("MONTH"),
        quarter(col("DATE")).alias("QUARTER"),
        # Weekend indicator
        when(dayofweek(col("DATE")).isin([1, 7]), lit(1)).otherwise(lit(0)).alias("IS_WEEKEND"),
        # Month end indicator (last 3 days of month)
        when(dayofmonth(col("DATE")) >= (dayofmonth(last_day(col("DATE"))) - lit(2)), lit(1))
        .otherwise(lit(0))
        .alias("IS_MONTH_END"),
    )

    # Calculate seasonal patterns (use date range from config to include generated data)
    seasonal_base_df = temporal_base_df.filter(col("DATE") >= lit(start_date))

    seasonal_patterns_df = seasonal_base_df.group_by("PUDO_ID", "DAY_OF_WEEK").agg(
        avg(col("FILL_RATE")).alias("AVG_FILL_RATE_BY_DOW"), stddev(col("FILL_RATE")).alias("STDDEV_FILL_RATE_BY_DOW")
    )

    # Join temporal features with seasonal patterns (use date range from config)
    # Note: FILL_RATE_DOW_DEVIATION removed to avoid data leakage (would need lagged FILL_RATE)
    final_temporal_df = (
        temporal_base_df.filter(col("DATE") >= lit(start_date))
        .join(seasonal_patterns_df, on=["PUDO_ID", "DAY_OF_WEEK"], how="left")
        .select(
            col("PUDO_ID"),
            col("DATE"),
            col("UPDATED_AT"),  # Include timestamp column
            col("DAY_OF_WEEK"),
            col("DAY_OF_MONTH"),
            col("MONTH"),
            col("QUARTER"),
            col("IS_WEEKEND"),
            col("IS_MONTH_END"),
            col("AVG_FILL_RATE_BY_DOW"),  # Historical average by day of week (ok, based on past data)
            col("STDDEV_FILL_RATE_BY_DOW"),  # Historical volatility (ok, based on past data)
        )
    )

    feature_view_kwargs = {
        "name": "PUDO__TEMPORAL_FEATURES",
        "entities": [entities["PUDO"]],
        "feature_df": final_temporal_df,
        "timestamp_col": "UPDATED_AT",
        "desc": "Temporal and seasonal pattern features",
    }

    # Add refresh configuration. Warehouse is only set when a schedule is configured
    # to prevent AUTO refresh without a schedule.
    if refresh_freq is not None:
        feature_view_kwargs["refresh_freq"] = refresh_freq
    if warehouse:
        feature_view_kwargs["warehouse"] = warehouse

    return FeatureView(**feature_view_kwargs)
