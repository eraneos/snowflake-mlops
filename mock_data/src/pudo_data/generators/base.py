"""Base generator class for PUDO data generation.

This module provides the abstract base class for all data generators in the PUDO
data generation system. It includes common functionality and utilities that are
shared across different types of generators.
"""

from abc import ABC, abstractmethod

import numpy as np
import polars as pl

from pudo_data.config_models import GenerationConfig


class BaseGenerator(ABC):
    """Abstract base class for all PUDO data generators.

    This class provides common functionality and utilities for generating synthetic
    PUDO-related data. All specific generators (PUDO, Parcels, Delivery Attempts,
    etc.) inherit from this base class.

    The base class handles random number generation with configurable seeds for
    reproducible results, and provides convenient methods for common random
    sampling operations.

    Attributes:
        config: GenerationConfig instance containing generation parameters.
        rng: NumPy random number generator with configured seed.

    Example:
        >>> config = GenerationConfig()
        >>> generator = PudoGenerator(config)
        >>> data = generator.generate()
    """

    def __init__(self, config: GenerationConfig, rng: np.random.Generator = None):
        """Initialize the base generator.

        Args:
            config: Configuration object containing generation parameters.
            rng: Optional NumPy random number generator. If None, creates a new
                generator using the seed from config.

        Example:
            >>> config = GenerationConfig(seed=42)
            >>> generator = BaseGenerator(config)
        """
        self.config = config
        self.rng = rng or np.random.default_rng(config.seed)

    @abstractmethod
    def generate(self) -> pl.DataFrame:
        """Generate the data.

        This method must be implemented by all concrete generator classes.
        It should return a Polars DataFrame containing the generated data.

        Returns:
            Polars DataFrame with generated data.

        Raises:
            NotImplementedError: If not implemented by subclass.
        """
        pass

    def validate(self, df: pl.DataFrame) -> bool:
        """Validate the generated data.

        Performs basic validation on the generated DataFrame. Subclasses can
        override this method to add specific validation logic.

        Args:
            df: DataFrame to validate.

        Returns:
            True if validation passes, False otherwise.

        Example:
            >>> df = pl.DataFrame({"col1": [1, 2, 3]})
            >>> generator.validate(df)
            True
        """
        return len(df) > 0

    def randint(self, low: int, high: int) -> int:
        """Generate random integer inclusive of both bounds.

        Wrapper around NumPy's random integers generation that ensures
        both bounds are inclusive.

        Args:
            low: Lower bound (inclusive).
            high: Upper bound (inclusive).

        Returns:
            Random integer between low and high (inclusive).

        Example:
            >>> generator.randint(1, 10)  # Random int from 1 to 10
            7
        """
        return int(self.rng.integers(low, high + 1))

    def choice(self, options: list, p: list | None = None):
        """Generate random choice from options.

        Wrapper around NumPy's random choice function using the configured
        random number generator.

        Args:
            options: List of options to choose from.
            p: Optional probability weights for each option.

        Returns:
            Randomly selected option from the list.

        Example:
            >>> options = ["A", "B", "C"]
            >>> generator.choice(options)
            'B'
        """
        return self.rng.choice(options, p=p)

    def uniform(self, low: float, high: float) -> float:
        """Generate random float between low and high.

        Args:
            low: Lower bound.
            high: Upper bound.

        Returns:
            Random float between low and high.

        Example:
            >>> generator.uniform(0.0, 1.0)  # Random float from 0.0 to 1.0
            0.54321
        """
        return self.rng.uniform(low, high)

    def normal(self, mean: float, std: float) -> float:
        """Generate random float from normal distribution.

        Args:
            mean: Mean of the normal distribution.
            std: Standard deviation of the normal distribution.

        Returns:
            Random float from normal distribution.

        Example:
            >>> generator.normal(10.0, 2.0)  # Normal with mean 10, std 2
            9.876
        """
        return self.rng.normal(mean, std)

    def exponential(self, scale: float) -> float:
        """Generate random float from exponential distribution.

        Args:
            scale: Scale parameter (1/λ) of the exponential distribution.

        Returns:
            Random float from exponential distribution.

        Example:
            >>> generator.exponential(2.0)  # Exponential with scale 2.0
            1.234
        """
        return self.rng.exponential(scale)
