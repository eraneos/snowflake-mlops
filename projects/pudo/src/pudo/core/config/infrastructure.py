"""Infrastructure configuration.

Infrastructure settings are loaded directly from config/infrastructure.yaml (no environment overrides).
This is a flat config file since infrastructure is shared across all environments.
"""

from pydantic import BaseModel

from pudo.core.config.utils import load_flat_yaml_config


class DatabaseConfig(BaseModel):
    """Database configuration."""

    name: str


class RoleConfig(BaseModel):
    """Role configuration."""

    name: str


class WarehouseConfig(BaseModel):
    """Warehouse configuration."""

    name: str
    size: str = "XSMALL"
    auto_suspend: int = 60
    auto_resume: bool = True


class ComputePoolConfig(BaseModel):
    """Compute pool configuration."""

    name: str
    min_nodes: int
    max_nodes: int
    instance_family: str
    auto_suspend_secs: int


class ComputePoolsConfig(BaseModel):
    """All compute pools configuration."""

    dev: ComputePoolConfig
    prod: ComputePoolConfig


class SharedDataConfig(BaseModel):
    """Shared data schema configuration."""

    schema_name: str
    description: str


class InfrastructureConfig(BaseModel):
    """Complete infrastructure configuration from config/infrastructure.yaml.

    This is a flat config (no environment overrides) since infrastructure
    is shared across all environments.
    """

    database: DatabaseConfig
    role: RoleConfig
    warehouse: WarehouseConfig
    compute_pools: ComputePoolsConfig
    shared_data: SharedDataConfig


# Auto-load infrastructure config (no environment overrides for infrastructure)
config = load_flat_yaml_config(InfrastructureConfig, "infrastructure.yaml")
