"""Feature view registry for automatic discovery and registration.

This module provides a decorator-based registry system that eliminates code duplication
between config files and Python code. Feature view creation functions are automatically
discovered by the registry.

Usage:
    @register_feature_view("pudo__historical_features")
    def create_pudo_historical_features(session, entities, refresh_freq, warehouse=None):
        ...

The registry will:
- Map config keys to creation functions automatically
- Derive Snowflake names from config keys (uppercase, preserving the ADR-0002
  ``<PROJECT>__<view>`` double-underscore namespace prefix)
- Enable adding new feature views without modifying ``pudo/feature_view/feature_store.py``
"""

from collections.abc import Callable

# Global registry: config_key -> creation_function
_FEATURE_VIEW_REGISTRY: dict[str, Callable] = {}


def register_feature_view(config_key: str):
    """Decorator to register a feature view creation function.

    Args:
        config_key: The key used in config/feature_view/feature_store/*.yaml
            (e.g., "pudo__historical_features"; ADR-0002 double-underscore namespace).

    Returns:
        Decorator function that registers the creation function

    Example:
        @register_feature_view("pudo__historical_features")
        def create_pudo_historical_features(session, entities, refresh_freq, warehouse=None):
            return FeatureView(...)
    """

    def decorator(func: Callable) -> Callable:
        _FEATURE_VIEW_REGISTRY[config_key] = func
        return func

    return decorator


def get_feature_view_creator(config_key: str) -> Callable | None:
    """Get the creation function for a feature view.

    Args:
        config_key: The key used in config files

    Returns:
        Creation function if registered, None otherwise
    """
    return _FEATURE_VIEW_REGISTRY.get(config_key)


def get_all_registered_keys() -> list[str]:
    """Get all registered feature view config keys.

    Returns:
        List of config keys for all registered feature views
    """
    return list(_FEATURE_VIEW_REGISTRY.keys())


def derive_snowflake_name(config_key: str) -> str:
    """Derive Snowflake feature view name from config key.

    Args:
        config_key: Config key like "pudo__historical_features"

    Returns:
        Snowflake name like "PUDO__HISTORICAL_FEATURES"
    """
    return config_key.upper()
