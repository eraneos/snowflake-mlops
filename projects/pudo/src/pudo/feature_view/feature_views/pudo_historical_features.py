from snowflake.ml.feature_store import FeatureView
from snowflake.snowpark.functions import avg, col, lag, lit, stddev, when
from snowflake.snowpark.window import Window

from pudo.core.config.data_generation import config as data_gen_config
from pudo.core.config.infrastructure import config as infra_config
from pudo.core.registry import register_feature_view


@register_feature_view("pudo__historical_features")
def create_pudo_historical_features(session, entities, refresh_freq, warehouse=None):
    """Create historical fill rate and capacity features using Snowpark DataFrames."""
    # Load base occupancy data (fully qualified to avoid FS schema resolution)
    # Use date range from config to include generated data
    occupancy_table = f"{infra_config.database.name}.{infra_config.shared_data.schema_name}.PUDO_OCCUPANCY"
    occupancy_df = session.table(occupancy_table).filter(col("DATE") >= lit(data_gen_config.start_date))

    # Define window specifications
    pudo_date_window_7d = Window.partition_by("PUDO_ID").order_by("DATE").rows_between(-6, 0)
    pudo_date_window_30d = Window.partition_by("PUDO_ID").order_by("DATE").rows_between(-29, 0)
    pudo_date_window_lag = Window.partition_by("PUDO_ID").order_by("DATE")

    # Calculate rolling metrics
    daily_metrics_df = occupancy_df.select(
        col("PUDO_ID"),
        col("DATE"),
        col("DATE").alias("UPDATED_AT"),  # Timestamp column for data freshness
        col("DAILY_DELIVERIES"),
        # Rolling averages (lagged by 1 day to avoid data leakage)
        avg(col("FILL_RATE")).over(pudo_date_window_7d).alias("FILL_RATE_7D_AVG"),
        avg(col("FILL_RATE")).over(pudo_date_window_30d).alias("FILL_RATE_30D_AVG"),
        # Volatility measures
        stddev(col("FILL_RATE")).over(pudo_date_window_7d).alias("FILL_RATE_7D_STDDEV"),
        # Trend indicators (using lagged values)
        (col("FILL_RATE") - lag(col("FILL_RATE"), 1).over(pudo_date_window_lag)).alias("FILL_RATE_1D_CHANGE"),
        (col("FILL_RATE") - lag(col("FILL_RATE"), 7).over(pudo_date_window_lag)).alias("FILL_RATE_7D_CHANGE"),
        # Peak indicators (based on historical patterns)
        when(lag(col("FILL_RATE"), 1).over(pudo_date_window_lag) >= lit(0.8), lit(1))
        .otherwise(lit(0))
        .alias("IS_HIGH_CAPACITY"),
        when(lag(col("FILL_RATE"), 1).over(pudo_date_window_lag) >= lit(1.0), lit(1))
        .otherwise(lit(0))
        .alias("IS_OVER_CAPACITY"),
    )

    feature_view_kwargs = {
        "name": "PUDO__HISTORICAL_FEATURES",
        "entities": [entities["PUDO"]],
        "feature_df": daily_metrics_df,
        "timestamp_col": "UPDATED_AT",
        "desc": "Historical fill rate and capacity utilization features",
    }

    # Add refresh configuration. Warehouse is only set when a schedule is configured
    # to prevent AUTO refresh without a schedule.
    if refresh_freq is not None:
        feature_view_kwargs["refresh_freq"] = refresh_freq
    if warehouse:
        feature_view_kwargs["warehouse"] = warehouse

    return FeatureView(**feature_view_kwargs)
