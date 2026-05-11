"""Data generators for synthetic PUDO datasets.

This package contains all the data generators used to create synthetic PUDO
(Pick-Up/Drop-Off) datasets for testing and development purposes. The generators
create realistic logistics data including PUDO locations, parcels, delivery
attempts, and occupancy information.

Submodules:
    base: Abstract base class providing common functionality for all generators.
    pudo: Generator for PUDO reference location data with Berlin geography.
    parcels: Generator for parcel delivery data with various sizes and weights.
    delivery_attempts: Generator for delivery attempt records and outcomes.
    occupancy: Generator for PUDO occupancy and utilization statistics.
"""
