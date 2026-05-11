"""PUDO reference data generator."""

import polars as pl

from pudo_data.generators.base import BaseGenerator


class PudoGenerator(BaseGenerator):
    """Generator for PUDO reference location data.

    This generator creates synthetic PUDO locations representing different types
    of pickup/drop-off points including parcel lockers, retail shops, and post
    offices. The locations are distributed within Berlin's geographic boundaries
    with realistic capacity ranges for each PUDO type.

    The generator uses the configured probabilities and capacity ranges to create
    diverse PUDO networks that reflect real-world logistics scenarios.

    Attributes:
        config: GenerationConfig instance with PUDO generation parameters.
        rng: NumPy random number generator for reproducible results.

    Example:
        >>> config = GenerationConfig(n_pudos=100)
        >>> generator = PudoGenerator(config)
        >>> pudo_data = generator.generate()
        >>> print(f"Generated {len(pudo_data)} PUDO locations")
    """

    def generate(self) -> pl.DataFrame:
        """Generate PUDO reference data with realistic Berlin locations.

        Creates PUDO locations distributed within Berlin's geographic boundaries.
        Each PUDO has a unique ID, name, type (SHOP, LOCKER, POST_OFFICE), geographic
        coordinates, address, capacity, and operating hours.

        The generator uses the configuration parameters to determine:
        - Geographic distribution within Berlin bounds
        - PUDO type probabilities (shop vs locker vs post office)
        - Capacity ranges for each PUDO type
        - Operating hours based on PUDO type

        Returns:
            Polars DataFrame containing PUDO reference data with columns:
            - PUDO_ID: Unique identifier (0 to n_pudos-1)
            - PUDO_NAME: Formatted name (PUDO_XXX)
            - PUDO_TYPE: Type of PUDO (SHOP, LOCKER, POST_OFFICE)
            - LATITUDE: Latitude coordinate (6 decimal precision)
            - LONGITUDE: Longitude coordinate (6 decimal precision)
            - ADDRESS: Formatted Berlin address
            - CAPACITY: Maximum parcel capacity
            - OPENING_HOURS: Operating hours string
            - IS_ACTIVE: Boolean flag (always True for generated PUDOs)

        Example:
            >>> generator = PudoGenerator(GenerationConfig(n_pudos=10))
            >>> df = generator.generate()
            >>> df.shape
            (10, 9)
            >>> df["PUDO_TYPE"].unique().to_list()
            ['SHOP', 'LOCKER', 'POST_OFFICE']
        """
        pudos = []

        for i in range(self.config.n_pudos):
            # Generate coordinates within Berlin bounds
            lat = self.rng.uniform(
                self.config.lat_center - self.config.lat_range / 2, self.config.lat_center + self.config.lat_range / 2
            )
            lon = self.rng.uniform(
                self.config.lon_center - self.config.lon_range / 2, self.config.lon_center + self.config.lon_range / 2
            )

            # Generate realistic PUDO characteristics using config
            pudo_type = self.rng.choice(["SHOP", "LOCKER", "POST_OFFICE"], p=self.config.get_pudo_type_probabilities())

            # Capacity based on type using config parameters
            if pudo_type == "LOCKER":
                capacity = self.rng.integers(
                    self.config.locker_capacity_min, self.config.locker_capacity_max + 1, endpoint=False
                )
            elif pudo_type == "SHOP":
                capacity = self.rng.integers(
                    self.config.shop_capacity_min, self.config.shop_capacity_max + 1, endpoint=False
                )
            else:  # POST_OFFICE
                capacity = self.rng.integers(
                    self.config.post_office_capacity_min, self.config.post_office_capacity_max + 1, endpoint=False
                )

            pudos.append(
                {
                    "PUDO_ID": i,
                    "PUDO_NAME": f"PUDO_{i:03d}",
                    "PUDO_TYPE": pudo_type,
                    "LATITUDE": round(lat, 6),
                    "LONGITUDE": round(lon, 6),
                    "ADDRESS": f"Berlin Street {i + 1}, 10{i % 100:02d} Berlin",
                    "CAPACITY": int(capacity),
                    "OPENING_HOURS": "08:00-20:00" if pudo_type == "SHOP" else "24/7",
                    "IS_ACTIVE": True,
                }
            )

        return pl.DataFrame(pudos)
