"""Hub infrastructure config loader.

Reads `hub/config/infrastructure.yaml` once at import time and exposes the
parsed pydantic model as `infra_config`. The YAML carries the resource names
fixed by ADR-0004 ("Platform Resources").

The config path is resolved from this file's location, so the loader works
regardless of the caller's working directory.
"""

from pathlib import Path

from pydantic import BaseModel
import yaml

HUB_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = HUB_ROOT / "config" / "infrastructure.yaml"


class DatabaseConfig(BaseModel):
    name: str


class RoleConfig(BaseModel):
    name: str


class WarehouseConfig(BaseModel):
    name: str
    size: str = "XSMALL"
    auto_suspend: int = 60
    auto_resume: bool = True


class ComputePoolConfig(BaseModel):
    name: str
    min_nodes: int
    max_nodes: int
    instance_family: str
    auto_suspend_secs: int


class ComputePoolsConfig(BaseModel):
    dev: ComputePoolConfig
    prod: ComputePoolConfig


class SharedDataConfig(BaseModel):
    schema_name: str
    description: str


class InfrastructureConfig(BaseModel):
    database: DatabaseConfig
    role: RoleConfig
    warehouse: WarehouseConfig
    compute_pools: ComputePoolsConfig
    shared_data: SharedDataConfig


def _load() -> InfrastructureConfig:
    if not CONFIG_PATH.is_file():
        msg = f"Hub infrastructure config not found at {CONFIG_PATH}"
        raise FileNotFoundError(msg)
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return InfrastructureConfig.model_validate(yaml.safe_load(f))


infra_config = _load()
