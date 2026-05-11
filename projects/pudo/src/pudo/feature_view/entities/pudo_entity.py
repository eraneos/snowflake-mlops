from snowflake.ml.feature_store import Entity


def create_pudo_entity():
    """Create PUDO entity for time series features."""
    return Entity(
        name="PUDO",
        join_keys=["PUDO_ID", "DATE"],
        desc="PUDO location and date composite entity for time series features",
    )
