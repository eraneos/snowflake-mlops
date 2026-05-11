"""YAML config loader for the PUDO project.

Resolves config files relative to ``projects/pudo/config/``. Two shapes are supported:

- Flat: a single YAML file (e.g. ``infrastructure.yaml``).
- Kustomize-style: ``<subdir>/base.yaml`` plus optional ``<subdir>/<env>.override.yaml``.

Callers pass the subdir explicitly, so the loader does not depend on caller-frame
inspection or the importing module's path.
"""

from pathlib import Path
from typing import Any, Literal, TypeVar

from deepmerge import Merger
from loguru import logger
from pydantic import BaseModel
import yaml

from pudo.core.environment import detect_environment

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CONFIG_DIR = PROJECT_ROOT / "config"

override_merger = Merger(
    [
        (list, ["override"]),
        (dict, ["merge"]),
        (set, ["override"]),
    ],
    ["override"],
    ["override"],
)

_ConfigModel = TypeVar("_ConfigModel", bound=BaseModel)


def load_flat_yaml_config(config_model: type[_ConfigModel], filename: str) -> _ConfigModel:
    """Load a flat YAML file from ``projects/pudo/config/<filename>``."""
    config_path = CONFIG_DIR / filename
    if not config_path.is_file():
        msg = f"Config file not found at {config_path}"
        raise FileNotFoundError(msg)

    with config_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    logger.info(f"Loaded flat config from {config_path}")
    return config_model.model_validate(data)


def load_yaml_config(
    config_model: type[_ConfigModel],
    subdir: str,
    environment: Literal["dev", "staging", "prod"] | None = None,
) -> _ConfigModel:
    """Load Kustomize-style base + env override from ``projects/pudo/config/<subdir>/``.

    Args:
        config_model: Pydantic model to validate into.
        subdir: Path relative to ``projects/pudo/config/`` (e.g. ``"training"``,
            ``"feature_view/feature_store"``).
        environment: Target env, or ``None`` to auto-detect from git.
    """
    if environment is None:
        environment = detect_environment()

    _config_dir = CONFIG_DIR / subdir
    base_settings_path = _config_dir / "base.yaml"
    override_path = _config_dir / f"{environment}.override.yaml"

    if not base_settings_path.is_file():
        msg = f"Base settings file not found at {base_settings_path}"
        raise FileNotFoundError(msg)

    with base_settings_path.open(encoding="utf-8") as f:
        config = config_model.model_validate(yaml.safe_load(f))

    logger.info(f"Loaded base config from {base_settings_path} for environment: {environment}")

    if override_path.is_file():
        with override_path.open(encoding="utf-8") as f:
            base_config = config.model_dump(round_trip=True)
            overrides: dict[str, Any] = yaml.safe_load(f) or {}
            combined = override_merger.merge(base_config, overrides)
            config = config_model(**combined)
            logger.info(f"Applied {environment} overrides from {override_path.as_posix()}")
    else:
        logger.debug(f"No overrides found at {override_path}, using base config only")

    return config
