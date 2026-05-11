"""Occupancy data generator.

This module contains the OccupancyGenerator class responsible for calculating
PUDO utilization statistics based on delivery attempt outcomes. It analyzes
successful PUDO deliveries to determine daily occupancy rates and utilization
patterns.
"""

import polars as pl

from pudo_data.generators.base import BaseGenerator


class OccupancyGenerator(BaseGenerator):
    """Generator for PUDO occupancy and utilization statistics.

    This generator calculates daily occupancy statistics for PUDO locations
    by analyzing successful PUDO deliveries from the delivery attempts data.
    It provides insights into capacity utilization patterns and fill rates
    that are essential for logistics planning and capacity optimization.

    The generator processes delivery attempts to:
    - Count daily deliveries per PUDO location
    - Calculate fill rates based on PUDO capacity
    - Generate time-series occupancy data for analysis
    - Identify utilization patterns and capacity constraints

    Attributes:
        config: GenerationConfig instance with generation parameters.
        pudo_df: DataFrame containing PUDO reference data and capacities.
        attempts_df: DataFrame containing delivery attempt outcomes.

    Example:
        >>> pudo_df = PudoGenerator(config).generate()
        >>> attempts_df = DeliveryAttemptsGenerator(config, pudo_df, parcels_df).generate()
        >>> generator = OccupancyGenerator(config, pudo_df, attempts_df)
        >>> occupancy_df = generator.generate()
    """

    def __init__(self, config, pudo_df: pl.DataFrame, attempts_df: pl.DataFrame):
        """Initialize occupancy generator with source data.

        Args:
            config: GenerationConfig instance with generation parameters.
            pudo_df: DataFrame containing PUDO locations and their capacities.
            attempts_df: DataFrame containing delivery attempt outcomes.
        """
        super().__init__(config)
        self.pudo_df = pudo_df
        self.attempts_df = attempts_df

    def generate(self) -> pl.DataFrame:
        """Generate PUDO occupancy statistics from delivery attempts.

        Calculates daily occupancy rates for each PUDO location by analyzing
        successful PUDO deliveries. Only considers parcels that were actually
        delivered to PUDO locations (DELIVERED_TO_PUDO status).

        The calculation process:
        1. Filter delivery attempts for successful PUDO deliveries
        2. Count daily deliveries per PUDO location
        3. Join with PUDO capacity data
        4. Calculate fill rates as daily_deliveries / capacity
        5. Generate time-series occupancy records

        Returns:
            Polars DataFrame containing occupancy data with columns:
            - PUDO_ID: PUDO location identifier
            - DATE: Date of occupancy measurement
            - DAILY_DELIVERIES: Number of parcels delivered to PUDO that day
            - FILL_RATE: Capacity utilization rate (0.0 to 1.0+)

        Note:
            Fill rates can exceed 1.0 if more parcels were delivered than
            the nominal capacity, indicating overflow conditions.

        Example:
            >>> generator = OccupancyGenerator(config, pudo_df, attempts_df)
            >>> occupancy_df = generator.generate()
            >>> occupancy_df.shape
            (1500, 4)  # 150 PUDOs, 10 days sample
            >>> occupancy_df["FILL_RATE"].describe()
            # Shows distribution of fill rates across all PUDOs and days
        """
        # Only count successful PUDO deliveries
        pudo_deliveries = self.attempts_df.filter(pl.col("DELIVERY_STATUS") == "DELIVERED_TO_PUDO")

        # Calculate daily deliveries per PUDO
        # Cast PUDO_ID to Int64 to ensure consistent types for join
        daily_deliveries = (
            pudo_deliveries.group_by(["PUDO_ID", "ATTEMPT_DATE"])
            .agg(pl.count("ATTEMPT_ID").alias("DAILY_DELIVERIES"))
            .with_columns(pl.col("PUDO_ID").cast(pl.Int64))
        )

        # Get PUDO capacities
        # Cast PUDO_ID to Int64 to ensure consistent types for join
        pudo_capacities = self.pudo_df.select(["PUDO_ID", "CAPACITY"]).with_columns(pl.col("PUDO_ID").cast(pl.Int64))

        # Join and calculate occupancy
        return (
            daily_deliveries.join(pudo_capacities, on="PUDO_ID")
            .with_columns(
                [
                    (pl.col("DAILY_DELIVERIES") / pl.col("CAPACITY")).alias("FILL_RATE"),
                    pl.col("ATTEMPT_DATE").alias("DATE"),
                ]
            )
            .select(["PUDO_ID", "DATE", "DAILY_DELIVERIES", "FILL_RATE"])
        )
