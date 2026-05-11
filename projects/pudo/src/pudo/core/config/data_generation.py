"""Data-generation parameters consumed by PUDO feature views.

Mock data ownership lives in the ``mock_data`` component; per ADR-0001 PUDO
carries its own copy of the values it needs (only ``start_date`` today).
"""

from datetime import date

from pydantic import BaseModel

from pudo.core.config.utils import load_flat_yaml_config


class DataGenerationConfig(BaseModel):
    start_date: date


config: DataGenerationConfig = load_flat_yaml_config(DataGenerationConfig, "data_generation.yaml")

__all__ = ["config", "DataGenerationConfig"]
