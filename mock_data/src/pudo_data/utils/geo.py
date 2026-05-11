"""Geospatial utilities for PUDO data generation.

This module provides geospatial utility functions for generating realistic
geographic data for PUDO (Pick-Up/Drop-Off) locations and delivery scenarios.
It includes distance calculations, clustered point generation, and Berlin-specific
geographic data.
"""

import numpy as np


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance between two points on Earth.

    Uses the Haversine formula to calculate the shortest distance over the Earth's
    surface between two geographic points specified by latitude and longitude.

    Args:
        lat1: Latitude of first point in decimal degrees.
        lon1: Longitude of first point in decimal degrees.
        lat2: Latitude of second point in decimal degrees.
        lon2: Longitude of second point in decimal degrees.

    Returns:
        Distance between the two points in kilometers.

    Example:
        >>> haversine_distance(52.5200, 13.4050, 52.5185, 13.4030)
        0.287
    """
    earth_radius = 6371.0  # Earth radius in km

    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    c = 2 * np.arcsin(np.sqrt(a))

    return earth_radius * c


def generate_clustered_points(
    n_points: int,
    n_clusters: int,
    center_lat: float,
    center_lon: float,
    lat_range: float,
    lon_range: float,
    cluster_std: float = 0.05,
    rng: np.random.Generator = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate geographically clustered points around specified centers.

    Creates realistic geographic distributions by generating cluster centers and
    then distributing points around them with normal distributions. This creates
    more realistic spatial patterns than uniform random distribution.

    Args:
        n_points: Total number of points to generate.
        n_clusters: Number of geographic clusters to create.
        center_lat: Center latitude for the overall area.
        center_lon: Center longitude for the overall area.
        lat_range: Latitude range (± from center) for the overall area.
        lon_range: Longitude range (± from center) for the overall area.
        cluster_std: Standard deviation for points within each cluster.
        rng: NumPy random number generator instance. If None, uses default.

    Returns:
        Tuple of (latitudes_array, longitudes_array) for generated points.

    Example:
        >>> lats, lons = generate_clustered_points(
        ...     n_points=100, n_clusters=5, center_lat=52.52, center_lon=13.405, lat_range=0.1, lon_range=0.1
        ... )
        >>> len(lats), len(lons)
        (100, 100)
    """
    if rng is None:
        rng = np.random.default_rng()

    # Create cluster centers
    cluster_lats = rng.normal(center_lat, lat_range / 3, n_clusters)
    cluster_lons = rng.normal(center_lon, lon_range / 3, n_clusters)

    # Assign points to clusters
    cluster_assignments = rng.integers(0, n_clusters, n_points)

    # Generate points around cluster centers
    lats = np.array([rng.normal(cluster_lats[c], cluster_std) for c in cluster_assignments])
    lons = np.array([rng.normal(cluster_lons[c], cluster_std) for c in cluster_assignments])

    # Clip to bounds
    lats = np.clip(lats, center_lat - lat_range / 2, center_lat + lat_range / 2)
    lons = np.clip(lons, center_lon - lon_range / 2, center_lon + lon_range / 2)

    return lats, lons


def get_berlin_postcodes() -> list[str]:
    """Get a list of realistic Berlin postal codes.

    Generates postal codes representing Berlin's 12 main districts with
    realistic code ranges for each district area.

    Returns:
        List of Berlin postal codes as strings in the format "XXXXX".

    Note:
        The returned codes cover the main Berlin districts including:
        - 10XXX: Mitte and surrounding areas
        - 12XXX: Schöneberg, Tempelhof, Steglitz
        - 13XXX: Wilmersdorf, Charlottenburg, Spandau

    Example:
        >>> postcodes = get_berlin_postcodes()
        >>> len(postcodes) > 0
        True
        >>> all(code.startswith(("10", "12", "13")) for code in postcodes[:5])
        True
    """
    return (
        [f"10{i:03d}" for i in range(115, 999, 50)]
        + [f"12{i:03d}" for i in range(43, 359, 30)]
        + [f"13{i:03d}" for i in range(51, 629, 40)]
    )
