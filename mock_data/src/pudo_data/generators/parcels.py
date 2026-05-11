"""Parcels data generator.

This module contains the ParcelsGenerator class responsible for generating
synthetic parcel data with realistic characteristics including destinations,
sizes, weights, and creation dates.
"""

from datetime import datetime, timedelta

import polars as pl

from pudo_data.generators.base import BaseGenerator


class ParcelsGenerator(BaseGenerator):
    """Generator for synthetic parcel delivery data.

    This generator creates realistic parcel data including tracking numbers,
    destinations within Berlin, parcel characteristics (size and weight),
    and creation timestamps. The parcels are generated over a specified
    time period with daily volume variations.

    The generator uses statistical distributions to create realistic:
    - Daily parcel volumes (normal distribution with 20% variance)
    - Geographic distribution of destinations within Berlin bounds
    - Parcel size distributions based on configuration
    - Weight distributions using exponential distribution

    Attributes:
        config: GenerationConfig instance with parcel generation parameters.
        rng: NumPy random number generator for reproducible results.

    Example:
        >>> config = GenerationConfig(n_days=30, avg_parcels_per_day=1000)
        >>> generator = ParcelsGenerator(config)
        >>> parcels_df = generator.generate()
        >>> print(f"Generated {len(parcels_df)} parcels")
    """

    def generate(self) -> pl.DataFrame:
        """Generate parcel data with realistic characteristics.

        Creates parcel records distributed over the configured time period
        with varying daily volumes and realistic destination and parcel
        characteristics.

        The generation process:
        1. Iterates through each day in the configured date range
        2. Generates daily parcel count with statistical variation
        3. Creates unique tracking numbers for each parcel
        4. Assigns random destinations within Berlin geographic bounds
        5. Assigns parcel sizes based on configured probabilities
        6. Generates weights using exponential distribution

        Returns:
            Polars DataFrame containing parcel data with columns:
            - TRACKING_NUMBER: Unique parcel identifier (DEXXXXXXXX format)
            - DESTINATION_LAT: Destination latitude (6 decimal precision)
            - DESTINATION_LON: Destination longitude (6 decimal precision)
            - DESTINATION_ADDRESS: Formatted destination address
            - PARCEL_SIZE: Size category (S, M, L)
            - WEIGHT_KG: Parcel weight in kilograms (2 decimal precision)
            - CREATED_DATE: Creation date as Python date object

        Example:
            >>> config = GenerationConfig(n_days=7, avg_parcels_per_day=100, start_date="2024-01-01")
            >>> generator = ParcelsGenerator(config)
            >>> df = generator.generate()
            >>> df.shape
            (700, 7)
            >>> df["PARCEL_SIZE"].unique().to_list()
            ['S', 'M', 'L']
        """
        start_date = datetime.strptime(self.config.start_date, "%Y-%m-%d")

        parcels = []
        tracking_counter = 0

        for day in range(self.config.n_days):
            current_date = start_date + timedelta(days=day)

            # Daily parcel volume with some randomness
            daily_parcels = int(self.rng.normal(self.config.avg_parcels_per_day, self.config.avg_parcels_per_day * 0.2))
            daily_parcels = max(10, daily_parcels)

            for _ in range(daily_parcels):
                # Generate random destination within Berlin
                dest_lat = self.rng.uniform(
                    self.config.lat_center - self.config.lat_range / 2,
                    self.config.lat_center + self.config.lat_range / 2,
                )
                dest_lon = self.rng.uniform(
                    self.config.lon_center - self.config.lon_range / 2,
                    self.config.lon_center + self.config.lon_range / 2,
                )

                tracking_number = f"DE{tracking_counter:08d}"
                destinaion_address = f"Berlin Address {tracking_counter}, 10{(tracking_counter % 100):02d} Berlin"

                parcels.append(
                    {
                        "TRACKING_NUMBER": tracking_number,
                        "DESTINATION_LAT": round(dest_lat, 6),
                        "DESTINATION_LON": round(dest_lon, 6),
                        "DESTINATION_ADDRESS": destinaion_address,
                        "PARCEL_SIZE": self.rng.choice(["S", "M", "L"], p=self.config.get_parcel_size_probabilities()),
                        "WEIGHT_KG": round(self.rng.exponential(self.config.weight_lambda), 2),
                        "CREATED_DATE": current_date.date(),  # Use Python date object for proper Pandas conversion
                    }
                )
                tracking_counter += 1

        return pl.DataFrame(parcels)
