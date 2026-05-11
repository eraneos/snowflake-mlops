"""Mock data infrastructure config loader.

Reads `mock_data/config/infrastructure.yaml` once at import time and exposes
the parsed pydantic model as `infra_config`. The YAML duplicates a subset of
hub's infrastructure config (per ADR-0001 component independence; ADR-0004
fixes the resource names). Mock data only reads these — hub remains the
canonical creator.
"""

from pathlib import Path

from pydantic import BaseModel
import yaml

MOCK_DATA_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = MOCK_DATA_ROOT / "config" / "infrastructure.yaml"


class DatabaseConfig(BaseModel):
    name: str


class RoleConfig(BaseModel):
    name: str


class WarehouseConfig(BaseModel):
    name: str


class SharedDataConfig(BaseModel):
    schema_name: str
    description: str


class InfrastructureConfig(BaseModel):
    database: DatabaseConfig
    role: RoleConfig
    warehouse: WarehouseConfig
    shared_data: SharedDataConfig


def _load() -> InfrastructureConfig:
    if not CONFIG_PATH.is_file():
        msg = f"mock_data infrastructure config not found at {CONFIG_PATH}"
        raise FileNotFoundError(msg)
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return InfrastructureConfig.model_validate(yaml.safe_load(f))


infra_config = _load()
