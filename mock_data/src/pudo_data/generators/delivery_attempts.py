"""Delivery attempts data generator."""

from datetime import date, datetime, timedelta

import numpy as np
import polars as pl

from pudo_data.generators.base import BaseGenerator


class DeliveryAttemptsGenerator(BaseGenerator):
    """Generator for delivery attempt events and outcomes.

    This generator simulates the complete delivery process for parcels including
    multiple delivery attempts, PUDO assignments, and various failure scenarios.
    It implements realistic delivery logistics with capacity constraints and
    geographic routing.

    The generator tracks PUDO capacity in real-time and makes intelligent
    assignments based on:
    - Geographic proximity to parcel destinations
    - Available capacity at PUDO locations
    - PUDO type preferences (24/7 access for lockers)
    - Configurable delivery success rates

    Key Features:
        - Multi-attempt delivery simulation (up to 3 attempts)
        - Real-time PUDO capacity tracking and management
        - Geographically-aware PUDO assignments
        - Configurable success rates and failure scenarios
        - Comprehensive delivery outcome tracking

    Attributes:
        config: GenerationConfig instance with delivery parameters.
        pudo_df: DataFrame containing PUDO reference data.
        parcels_df: DataFrame containing parcel data.
        daily_assignments: Dictionary tracking daily PUDO capacity usage.
        pudo_lookup: Fast lookup dictionary for PUDO characteristics.

    Example:
        >>> pudo_df = PudoGenerator(config).generate()
        >>> parcels_df = ParcelsGenerator(config).generate()
        >>> generator = DeliveryAttemptsGenerator(config, pudo_df, parcels_df)
        >>> attempts_df = generator.generate()
    """

    def __init__(self, config, pudo_df: pl.DataFrame, parcels_df: pl.DataFrame):
        """Initialize delivery attempts generator with dependencies.

        Args:
            config: GenerationConfig instance with delivery parameters.
            pudo_df: DataFrame containing PUDO reference locations and capacities.
            parcels_df: DataFrame containing parcels to be delivered.

        The constructor builds efficient lookup structures for PUDO data and
        initializes capacity tracking for realistic delivery simulation.
        """
        super().__init__(config)
        self.pudo_df = pudo_df
        self.parcels_df = parcels_df
        # Track daily assignments to calculate real-time capacity
        self.daily_assignments = {}
        # Create PUDO lookup for faster access (works with both 9 and 10 column dataframes)
        self.pudo_lookup = {
            row[0]: {"capacity": row[6], "type": row[2], "lat": row[3], "lon": row[4]}
            for row in self.pudo_df.iter_rows()
        }

    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate approximate distance in km using Euclidean distance."""
        lat_diff = (lat1 - lat2) * 111
        lon_diff = (lon1 - lon2) * 64
        return (lat_diff**2 + lon_diff**2) ** 0.5

    def _get_candidate_pudos(self, dest_lat: float, dest_lon: float, max_distance_km: float = 5.0) -> pl.DataFrame:
        """Get PUDOs within reasonable distance of destination that have available capacity."""
        candidates = []

        for row in self.pudo_df.iter_rows():
            # Handle both generated dataframes (9 cols) and Snowflake reads (10 cols with CREATED_AT)
            if len(row) == 10:
                pudo_id, _name, pudo_type, lat, lon, _address, capacity, _hours, is_active, _created_at = row
            else:
                pudo_id, _name, pudo_type, lat, lon, _address, capacity, _hours, is_active = row

            if not is_active:
                continue

            distance = self._calculate_distance(dest_lat, dest_lon, lat, lon)

            if distance <= max_distance_km:
                candidates.append(
                    {
                        "PUDO_ID": pudo_id,
                        "PUDO_TYPE": pudo_type,
                        "LATITUDE": lat,
                        "LONGITUDE": lon,
                        "CAPACITY": capacity,
                        "DISTANCE_KM": distance,
                    }
                )

        return pl.DataFrame(candidates) if candidates else pl.DataFrame()

    def _get_available_pudos(self, candidates: pl.DataFrame, delivery_date: str) -> pl.DataFrame:
        """Filter candidates to only include PUDOs with available capacity."""
        if len(candidates) == 0:
            return candidates

        available = []

        for row in candidates.iter_rows():
            pudo_id, pudo_type, lat, lon, capacity, distance = row
            current_occupancy = self._get_current_occupancy(pudo_id, delivery_date)

            # Only include PUDOs that are not at full capacity
            if current_occupancy < capacity:
                available.append(
                    {
                        "PUDO_ID": pudo_id,
                        "PUDO_TYPE": pudo_type,
                        "LATITUDE": lat,
                        "LONGITUDE": lon,
                        "CAPACITY": capacity,
                        "DISTANCE_KM": distance,
                        "CURRENT_OCCUPANCY": current_occupancy,
                        "AVAILABLE_CAPACITY": capacity - current_occupancy,
                    }
                )

        return pl.DataFrame(available) if available else pl.DataFrame()

    def _get_current_occupancy(self, pudo_id: int, date: str) -> int:
        """Get current number of assignments for a PUDO on a given date."""
        date_key = f"{pudo_id}_{date}"
        return self.daily_assignments.get(date_key, 0)

    def _update_occupancy(self, pudo_id: int, date: str):
        """Update the assignment count for a PUDO on a given date."""
        date_key = f"{pudo_id}_{date}"
        self.daily_assignments[date_key] = self.daily_assignments.get(date_key, 0) + 1

    def _calculate_assignment_weights(self, available_pudos: pl.DataFrame) -> np.ndarray:
        """Calculate assignment weights based on distance and remaining capacity."""
        if len(available_pudos) == 0:
            return np.array([])

        weights = []

        for row in available_pudos.iter_rows():
            _pudo_id, pudo_type, _lat, _lon, capacity, distance, current_occupancy, _available_capacity = row

            # Distance factor (closer = better, exponential decay)
            distance_weight = np.exp(-distance / 2.0)

            # Capacity factor (more available capacity = better)
            capacity_utilization = current_occupancy / capacity
            capacity_weight = 1.0 - capacity_utilization  # Higher weight for less utilized PUDOs

            # PUDO type preference (24/7 lockers slightly preferred)
            type_weight = 1.2 if pudo_type == "LOCKER" else 1.0

            # Combined weight
            total_weight = distance_weight * capacity_weight * type_weight

            weights.append(total_weight)

        weights = np.array(weights)

        # Normalize to probabilities
        return weights / weights.sum() if weights.sum() > 0 else np.ones(len(weights)) / len(weights)

    def _assign_pudo(self, dest_lat: float, dest_lon: float, delivery_date: str) -> int | None:
        """Assign PUDO using geospatial zones and capacity weighting with strict capacity limits."""

        # Try nearby PUDOs first (5km radius)
        candidates = self._get_candidate_pudos(dest_lat, dest_lon, max_distance_km=5.0)
        available_pudos = self._get_available_pudos(candidates, delivery_date)

        # If no available nearby PUDOs, expand search (10km radius)
        if len(available_pudos) == 0:
            candidates = self._get_candidate_pudos(dest_lat, dest_lon, max_distance_km=10.0)
            available_pudos = self._get_available_pudos(candidates, delivery_date)

        # If still no available PUDOs, search all active PUDOs
        if len(available_pudos) == 0:
            candidates = self._get_candidate_pudos(dest_lat, dest_lon, max_distance_km=50.0)  # City-wide search
            available_pudos = self._get_available_pudos(candidates, delivery_date)

        # If absolutely no capacity available anywhere, return None (delivery fails)
        if len(available_pudos) == 0:
            return None

        # Calculate weights and select PUDO
        weights = self._calculate_assignment_weights(available_pudos)
        pudo_ids = available_pudos["PUDO_ID"].to_numpy()

        selected_pudo = int(self.rng.choice(pudo_ids, p=weights))

        self._update_occupancy(selected_pudo, delivery_date)
        return selected_pudo

    def _generate_parcel_attempts(self, parcel_row: tuple) -> list:
        """Generate complete delivery lifecycle for a single parcel.

        Simulates up to 3 delivery attempts for a parcel with realistic
        success/failure outcomes based on configured success rates. If home
        delivery fails, attempts to redirect to an available PUDO location.

        Args:
            parcel_row: Tuple containing parcel data (tracking_number, dest_lat,
                       dest_lon, dest_address, parcel_size, weight_kg, created_date).

        Returns:
            List of attempt records for this parcel's delivery lifecycle.
        """
        tracking_number, dest_lat, dest_lon, _dest_address, _parcel_size, _weight_kg, created_date = parcel_row

        attempts = []

        # Start delivery attempts on creation date
        # Handle both date objects and strings
        if isinstance(created_date, date):
            current_date = datetime.combine(created_date, datetime.min.time())
        else:
            current_date = datetime.strptime(created_date, "%Y-%m-%d")
        attempt_number = 1
        delivered = False

        # Use configurable success rates
        success_rates = self.config.get_delivery_success_rates()

        while not delivered and attempt_number <= 3:
            if attempt_number == 1:
                success = self.rng.random() < success_rates[0]
            elif attempt_number == 2:
                success = self.rng.random() < success_rates[1] / (1 - success_rates[0])
            else:  # attempt 3 - try to go to PUDO
                success = False

            if success:
                # Successful delivery to customer
                attempts.append(
                    {
                        "ATTEMPT_ID": f"{tracking_number}_A{attempt_number}",
                        "TRACKING_NUMBER": tracking_number,
                        "ATTEMPT_DATE": current_date.date(),  # Use Python date object
                        "ATTEMPT_NUMBER": attempt_number,
                        "DELIVERY_STATUS": "DELIVERED_TO_CUSTOMER",
                        "PUDO_ID": None,
                        "DRIVER_ID": int(self.rng.integers(1, 51)),
                        "ATTEMPT_TIME": f"{self.rng.integers(9, 19):02d}:{self.rng.integers(0, 60):02d}",
                        "FAILURE_REASON": None,
                    }
                )
                delivered = True
            else:
                if attempt_number < 3:
                    # Failed attempt
                    failure_reasons = ["NOT_HOME", "ADDRESS_ISSUE", "ACCESS_DENIED", "REFUSED"]
                    attempts.append(
                        {
                            "ATTEMPT_ID": f"{tracking_number}_A{attempt_number}",
                            "TRACKING_NUMBER": tracking_number,
                            "ATTEMPT_DATE": current_date.date(),  # Use Python date object
                            "ATTEMPT_NUMBER": attempt_number,
                            "DELIVERY_STATUS": "ATTEMPTED",
                            "PUDO_ID": None,
                            "DRIVER_ID": int(self.rng.integers(1, 51)),
                            "ATTEMPT_TIME": f"{self.rng.integers(9, 19):02d}:{self.rng.integers(0, 60):02d}",
                            "FAILURE_REASON": self.rng.choice(failure_reasons),
                        }
                    )
                    # Next attempt tomorrow
                    current_date += timedelta(days=1)
                    attempt_number += 1
                else:
                    # Final attempt - try to send to PUDO
                    current_date_str = current_date.strftime("%Y-%m-%d")
                    pudo_id = self._assign_pudo(dest_lat, dest_lon, current_date_str)

                    if pudo_id is not None:
                        # Successfully assigned to PUDO
                        attempts.append(
                            {
                                "ATTEMPT_ID": f"{tracking_number}_A{attempt_number}",
                                "TRACKING_NUMBER": tracking_number,
                                "ATTEMPT_DATE": current_date.date(),  # Use Python date object
                                "ATTEMPT_NUMBER": attempt_number,
                                "DELIVERY_STATUS": "DELIVERED_TO_PUDO",
                                "PUDO_ID": pudo_id,
                                "DRIVER_ID": int(self.rng.integers(1, 51)),
                                "ATTEMPT_TIME": f"{self.rng.integers(9, 19):02d}:{self.rng.integers(0, 60):02d}",
                                "FAILURE_REASON": "MAX_ATTEMPTS_REACHED",
                            }
                        )
                    else:
                        # No PUDO capacity available - delivery fails
                        attempts.append(
                            {
                                "ATTEMPT_ID": f"{tracking_number}_A{attempt_number}",
                                "TRACKING_NUMBER": tracking_number,
                                "ATTEMPT_DATE": current_date.date(),  # Use Python date object
                                "ATTEMPT_NUMBER": attempt_number,
                                "DELIVERY_STATUS": "FAILED_NO_CAPACITY",
                                "PUDO_ID": None,
                                "DRIVER_ID": int(self.rng.integers(1, 51)),
                                "ATTEMPT_TIME": f"{self.rng.integers(9, 19):02d}:{self.rng.integers(0, 60):02d}",
                                "FAILURE_REASON": "NO_PUDO_CAPACITY",
                            }
                        )

                    delivered = True

        return attempts

    def generate(self) -> pl.DataFrame:
        """Generate comprehensive delivery attempts data for all parcels.

        Simulates the complete delivery lifecycle for each parcel including
        multiple delivery attempts, PUDO redirections, and final outcomes.
        The method tracks PUDO capacity utilization in real-time to ensure
        realistic capacity constraints.

        Process Overview:
        1. Reset capacity tracking for fresh generation
        2. Process each parcel through delivery attempt simulation
        3. Generate up to 3 delivery attempts per parcel
        4. Apply success rates and capacity constraints
        5. Assign PUDOs when home delivery fails

        Returns:
            Polars DataFrame containing delivery attempt records with columns:
            - ATTEMPT_ID: Unique attempt identifier (TRACKING_A#)
            - TRACKING_NUMBER: Associated parcel tracking number
            - ATTEMPT_DATE: Date of delivery attempt
            - ATTEMPT_NUMBER: Attempt sequence (1, 2, or 3)
            - DELIVERY_STATUS: Outcome status (DELIVERED_TO_CUSTOMER, ATTEMPTED, etc.)
            - PUDO_ID: Assigned PUDO location (if applicable)
            - DRIVER_ID: Assigned delivery driver (1-50)
            - ATTEMPT_TIME: Time of delivery attempt (HH:MM)
            - FAILURE_REASON: Reason for failure (if applicable)

        Example:
            >>> generator = DeliveryAttemptsGenerator(config, pudo_df, parcels_df)
            >>> attempts_df = generator.generate()
            >>> attempts_df.shape
            (5000, 9)
            >>> attempts_df["DELIVERY_STATUS"].unique().to_list()
            ['DELIVERED_TO_CUSTOMER', 'ATTEMPTED', 'DELIVERED_TO_PUDO', 'FAILED_NO_CAPACITY']
        """
        # Reset daily assignments
        self.daily_assignments = {}

        all_attempts = []

        # Generate attempts for each parcel
        for parcel_row in self.parcels_df.iter_rows():
            parcel_attempts = self._generate_parcel_attempts(parcel_row)
            all_attempts.extend(parcel_attempts)

        return pl.DataFrame(all_attempts)
