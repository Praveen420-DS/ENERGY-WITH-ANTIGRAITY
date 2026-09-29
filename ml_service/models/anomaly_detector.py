"""Robust per-meter outlier detection for observed energy history."""
from collections import defaultdict
from statistics import median
from typing import Iterable, Mapping


class AnomalyDetector:
    """Detect consumption outliers with a Gaussian-scaled MAD score."""

    def detect(self, data: Iterable[Mapping], threshold: float = 3.5) -> list[dict]:
        groups: dict[int, list[Mapping]] = defaultdict(list)
        for row in data:
            groups[int(row["meter_id"])].append(row)
        detected = []
        for meter_id, records in groups.items():
            values = [float(row["consumption_kwh"]) for row in records]
            center = median(values)
            scale = 1.4826 * median([abs(value - center) for value in values])
            if scale == 0:
                continue
            for row, value in zip(records, values):
                score = abs(value - center) / scale
                if score < threshold:
                    continue
                deviation = 0.0 if center == 0 else (value - center) / abs(center) * 100
                detected.append({
                    "meter_id": meter_id, "timestamp": row["timestamp"],
                    "anomaly_type": "spike" if value > center else "drop",
                    "severity": "high" if score >= threshold * 1.5 else "medium",
                    "actual_kwh": value, "expected_kwh": center,
                    "deviation_pct": deviation,
                    "description": f"Robust deviation score: {score:.2f}.",
                })
        return detected
