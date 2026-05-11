"""PUDO (Pick-Up/Drop-Off) data generation and management package.

This package provides comprehensive functionality for generating synthetic PUDO data
for testing and development purposes. It includes data generators for creating
realistic parcel delivery scenarios, PUDO location data, delivery attempts, and
occupancy information.

The package is designed for Berlin-based logistics scenarios and generates data
that can be used for capacity planning, delivery optimization, and analytics
modeling.

Key Features:
    - Synthetic data generation for PUDO networks
    - Realistic Berlin geography-based location generation
    - Configurable delivery scenarios and success rates
    - Snowflake database integration for data storage
    - Command-line interface for easy data management

Example:
    Basic usage for generating and uploading data:

    >>> from pudo_data.config import get_generation_config
    >>> from pudo_data.generators.pudo import PudoGenerator
    >>> from pudo_data.generators.parcels import ParcelsGenerator
    >>>
    >>> config = get_generation_config()
    >>> pudo_gen = PudoGenerator(config)
    >>> pudo_data = pudo_gen.generate()
    >>> print(f"Generated {len(pudo_data)} PUDO locations")

    CLI usage:

    >>> pudo-generate generate --upload  # Generate and upload to Snowflake
    >>> pudo-generate inspect             # Generate and inspect data locally
"""
