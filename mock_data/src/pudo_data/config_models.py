"""Configuration management for PUDO data generation.

This module provides config access for PUDO data generation.
"""

from pathlib import Path

from pydantic import BaseModel, Field
import yaml


class GeographyConfig(BaseModel):
    """Geographic bounds configuration."""

    lat_center: float = Field(..., description="Latitude center point")
    lon_center: float = Field(..., description="Longitude center point")
    lat_range: float = Field(..., description="Latitude range")
    lon_range: float = Field(..., description="Longitude range")


class CapacityRangeConfig(BaseModel):
    """Capacity range for a PUDO type."""

    min_capacity: int = Field(..., alias="min", description="Minimum capacity")
    max_capacity: int = Field(..., alias="max", description="Maximum capacity")


class CapacityConfig(BaseModel):
    """PUDO capacity ranges by type."""

    locker: CapacityRangeConfig
    shop: CapacityRangeConfig
    post_office: CapacityRangeConfig


class PUDODistributionConfig(BaseModel):
    """PUDO type distribution probabilities."""

    shop_probability: float = Field(..., ge=0, le=1)
    locker_probability: float = Field(..., ge=0, le=1)
    post_office_probability: float = Field(..., ge=0, le=1)


class DeliverySuccessConfig(BaseModel):
    """Delivery success rates."""

    first_attempt_success_rate: float = Field(..., ge=0, le=1)
    second_attempt_success_rate: float = Field(..., ge=0, le=1)
    pudo_redirection_rate: float = Field(..., ge=0, le=1)


class ParcelDistributionConfig(BaseModel):
    """Parcel size distribution probabilities."""

    small_probability: float = Field(..., ge=0, le=1)
    medium_probability: float = Field(..., ge=0, le=1)
    large_probability: float = Field(..., ge=0, le=1)


class WeightConfig(BaseModel):
    """Weight distribution parameters."""

    lambda_: float = Field(..., alias="lambda", description="Exponential distribution parameter")


class GenerationConfig(BaseModel):
    """Complete data generation configuration."""

    # Dataset size configuration
    n_pudos: int = Field(..., description="Number of PUDO locations")
    n_days: int = Field(..., description="Number of days to generate")
    avg_parcels_per_day: int = Field(..., description="Average parcels per day")
    random_seed: int = Field(..., description="Random seed for reproducibility")
    start_date: str = Field(..., description="Start date for data generation")

    # Nested configurations
    geography: GeographyConfig
    capacity: CapacityConfig
    pudo_distribution: PUDODistributionConfig
    delivery_success: DeliverySuccessConfig
    parcel_distribution: ParcelDistributionConfig
    weight: WeightConfig

    class Config:
        populate_by_name = True  # Allow field population by alias

    # Backward compatibility properties for generators
    @property
    def seed(self) -> int:
        """Alias for random_seed for backward compatibility."""
        return self.random_seed

    @property
    def lat_center(self) -> float:
        """Geography latitude center."""
        return self.geography.lat_center

    @property
    def lon_center(self) -> float:
        """Geography longitude center."""
        return self.geography.lon_center

    @property
    def lat_range(self) -> float:
        """Geography latitude range."""
        return self.geography.lat_range

    @property
    def lon_range(self) -> float:
        """Geography longitude range."""
        return self.geography.lon_range

    @property
    def locker_capacity_min(self) -> int:
        """Locker minimum capacity."""
        return self.capacity.locker.min_capacity

    @property
    def locker_capacity_max(self) -> int:
        """Locker maximum capacity."""
        return self.capacity.locker.max_capacity

    @property
    def shop_capacity_min(self) -> int:
        """Shop minimum capacity."""
        return self.capacity.shop.min_capacity

    @property
    def shop_capacity_max(self) -> int:
        """Shop maximum capacity."""
        return self.capacity.shop.max_capacity

    @property
    def post_office_capacity_min(self) -> int:
        """Post office minimum capacity."""
        return self.capacity.post_office.min_capacity

    @property
    def post_office_capacity_max(self) -> int:
        """Post office maximum capacity."""
        return self.capacity.post_office.max_capacity

    @property
    def weight_lambda(self) -> float:
        """Weight distribution lambda parameter."""
        return self.weight.lambda_

    def get_pudo_type_probabilities(self) -> list[float]:
        """Get PUDO type probabilities as list [shop, locker, post_office]."""
        return [
            self.pudo_distribution.shop_probability,
            self.pudo_distribution.locker_probability,
            self.pudo_distribution.post_office_probability,
        ]

    def get_parcel_size_probabilities(self) -> list[float]:
        """Get parcel size probabilities as list [small, medium, large]."""
        return [
            self.parcel_distribution.small_probability,
            self.parcel_distribution.medium_probability,
            self.parcel_distribution.large_probability,
        ]

    def get_delivery_success_rates(self) -> list[float]:
        """Get delivery success rates as list [first_attempt, second_attempt, pudo_redirection]."""
        return [
            self.delivery_success.first_attempt_success_rate,
            self.delivery_success.second_attempt_success_rate,
            self.delivery_success.pudo_redirection_rate,
        ]


def get_generation_config() -> GenerationConfig:
    """Get data generation configuration from `mock_data/config/data_generation.yaml`."""
    config_path = Path(__file__).resolve().parents[2] / "config" / "data_generation.yaml"

    if not config_path.exists():
        msg = f"Data generation config not found at {config_path}"
        raise FileNotFoundError(msg)

    with config_path.open() as f:
        config_data = yaml.safe_load(f)

    return GenerationConfig(**config_data)
