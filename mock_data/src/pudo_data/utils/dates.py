"""Date and time utilities for PUDO data generation.

This module provides utility functions for handling dates and time-related
operations in the PUDO data generation process.
"""

from datetime import datetime, timedelta


def generate_date_range(start_date: str, n_days: int) -> list[str]:
    """Generate a list of consecutive dates starting from a given date.

    Args:
        start_date: Starting date in YYYY-MM-DD format.
        n_days: Number of days to generate (including start_date).

    Returns:
        List of date strings in YYYY-MM-DD format.

    Example:
        >>> generate_date_range("2024-01-01", 5)
        ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05']
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    return [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n_days)]


def is_weekend(date_str: str) -> bool:
    """Check if a given date falls on a weekend.

    Args:
        date_str: Date string in YYYY-MM-DD format.

    Returns:
        True if the date is Saturday or Sunday, False otherwise.

    Example:
        >>> is_weekend("2024-01-06")  # Saturday
        True
        >>> is_weekend("2024-01-07")  # Sunday
        True
        >>> is_weekend("2024-01-08")  # Monday
        False
    """
    date = datetime.strptime(date_str, "%Y-%m-%d")
    return date.weekday() >= 5  # Saturday = 5, Sunday = 6
