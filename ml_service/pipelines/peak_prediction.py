"""Short outlook forecast based on observed meter readings."""

from datetime import timedelta
from math import isfinite
from statistics import median
from typing import Iterable, Mapping


class PeakPredictor:
    """Estimate future readings from recent trend and identify the outlook peak.

    The horizon is a count of future sampling intervals. The mean consumption
    change over the last three observed intervals is extrapolated, and the
    largest estimated future reading and its timestamp are returned.
    """

    def predict(self, history: Iterable[Mapping], horizon: int = 1) -> dict:
        if not isinstance(horizon, int) or not 1 <= horizon <= 24:
            raise ValueError("Forecast horizon must be between 1 and 24 records.")
        records = list(history)
        if len(records) < 3:
            raise ValueError("At least three valid historical energy records are required.")
        try:
            records.sort(key=lambda row: row["timestamp"])
        except (KeyError, TypeError) as exc:
            raise ValueError("Every historical record must include a valid timestamp.") from exc

        values = [float(row["consumption_kwh"]) for row in records]
        if any(not isfinite(value) or value < 0 for value in values):
            raise ValueError("Historical consumption values must be finite and non-negative.")
        timestamps = [row["timestamp"] for row in records]
        intervals = [right - left for left, right in zip(timestamps, timestamps[1:])]
        if any(interval <= timedelta(0) for interval in intervals):
            raise ValueError("Historical timestamps must be distinct and increasing.")

        recent_values = values[-4:]
        recent_intervals = intervals[-3:]
        interval_seconds = median([item.total_seconds() for item in recent_intervals])
        changes = [right - left for left, right in zip(recent_values, recent_values[1:])]
        average_change = sum(changes) / len(changes)
        forecasts = [
            max(0.0, values[-1] + average_change * step)
            for step in range(1, horizon + 1)
        ]
        peak_index = max(
            range(len(forecasts)), key=lambda index: (forecasts[index], -index)
        )
        baseline = median(values)
        ordered = sorted(values)
        peak_threshold = ordered[min(len(ordered) - 1, int(0.9 * len(ordered)))]
        return {
            "forecast_kwh": forecasts[peak_index],
            "peak_timestamp": timestamps[-1]
            + timedelta(seconds=interval_seconds * (peak_index + 1)),
            "peak_threshold_kwh": peak_threshold,
            "is_peak_likely": forecasts[peak_index] >= peak_threshold,
            "baseline_kwh": baseline,
            "horizon_records": horizon,
            "history_records": len(values),
        }
