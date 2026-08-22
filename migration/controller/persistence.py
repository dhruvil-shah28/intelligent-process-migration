#!/usr/bin/env python3

import time


class PressurePersistence:
    """
    Tracks how long resource pressure remains elevated.

    This prevents transient spikes from immediately
    triggering migration decisions.
    """

    def __init__(
        self,
        monitor_threshold=0.50,
        migrate_threshold=0.75,
        persistence_seconds=10.0,
    ):
        self.monitor_threshold = monitor_threshold
        self.migrate_threshold = migrate_threshold
        self.persistence_seconds = persistence_seconds

        self.pressure_since = None
        self.last_score = 0.0

    def update(self, score, now=None):
        """
        Update persistence state using the latest score.
        """

        if now is None:
            now = time.monotonic()

        self.last_score = score

        elevated = score >= self.monitor_threshold

        if not elevated:
            self.pressure_since = None

            return {
                "score": score,
                "pressure_active": False,
                "pressure_duration_seconds": 0.0,
                "persistent": False,
                "temporal_confidence": 0.0,
            }

        if self.pressure_since is None:
            self.pressure_since = now

        duration = now - self.pressure_since

        persistent = duration >= self.persistence_seconds

        temporal_confidence = min(
            duration / self.persistence_seconds,
            1.0,
        )

        return {
            "score": score,
            "pressure_active": True,
            "pressure_duration_seconds": round(
                duration,
                3,
            ),
            "persistent": persistent,
            "temporal_confidence": round(
                temporal_confidence,
                4,
            ),
        }
