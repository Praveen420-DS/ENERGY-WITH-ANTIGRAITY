"""OpenWeather client and normalized weather values for the V3.1 flow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import re
from typing import Any, Literal
from urllib.parse import urljoin

import httpx

from app.config import Settings


class _OpenWeatherLogRedaction(logging.Filter):
    """Redact OpenWeather query credentials from HTTPX request log lines."""

    _APPID = re.compile(r"([?&]appid=)[^&\s]+", re.IGNORECASE)

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        sanitized = self._APPID.sub(r"\1[REDACTED]", message)
        if sanitized != message:
            record.msg = sanitized
            record.args = ()
        return True


# HTTPX logs complete URLs, including query parameters, at INFO. Keep its
# standard request logging safe even though OpenWeather requires appid in URL.
_HTTPX_LOGGER = logging.getLogger("httpx")
if not any(isinstance(item, _OpenWeatherLogRedaction) for item in _HTTPX_LOGGER.filters):
    _HTTPX_LOGGER.addFilter(_OpenWeatherLogRedaction())

WeatherMode = Literal["current", "forecast"]


class WeatherProviderError(Exception):
    """Safe provider failure; messages deliberately contain no request detail."""


@dataclass(frozen=True)
class NormalizedWeather:
    """Seven production model weather inputs plus acquisition provenance.

    Units match the ASHRAE fields used to train v1.0.0: Celsius, oktas (0–9),
    inches for hourly precipitation, hPa, degrees, and m/s. OpenWeather metric
    mode supplies Celsius/m/s and hPa; clouds percent are scaled to oktas and
    rain mm is converted to inches. Missing provider fields stay None.
    """

    air_temperature: float | None
    cloud_coverage: float | None
    dew_temperature: float | None
    precip_depth_1_hr: float | None
    sea_level_pressure: float | None
    wind_direction: float | None
    wind_speed: float | None
    provider: str
    retrieved_at: datetime
    source_latitude: float
    source_longitude: float
    observation_at: datetime | None
    mode: WeatherMode


class OpenWeatherProvider:
    """Small async OpenWeather client. An HTTPX client can be injected in tests."""

    _ENDPOINTS: dict[WeatherMode, str] = {
        "current": "weather",
        "forecast": "forecast",
    }

    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        self._settings = settings
        self._client = client
        self._timeout = httpx.Timeout(timeout_seconds)

    async def retrieve(
        self, latitude: float, longitude: float, *, mode: WeatherMode = "current"
    ) -> NormalizedWeather:
        """Retrieve current conditions or the nearest forecast record."""
        if mode not in self._ENDPOINTS:
            raise ValueError("Unsupported weather retrieval mode.")
        if not self._settings.weather_api_key.get_secret_value():
            raise WeatherProviderError("Weather provider is not configured.")

        base = self._settings.weather_api_url.rstrip("/") + "/"
        endpoint = urljoin(base, self._ENDPOINTS[mode])
        params = {
            "lat": latitude,
            "lon": longitude,
            "appid": self._settings.weather_api_key.get_secret_value(),
            "units": "metric",
        }
        try:
            if self._client is None:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.get(endpoint, params=params)
            else:
                response = await self._client.get(
                    endpoint, params=params, timeout=self._timeout
                )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            # Provider/HTTP exceptions may embed the full URL including appid.
            raise WeatherProviderError("Weather provider request failed.") from None

        try:
            record = payload
            if mode == "forecast":
                records = payload["list"]
                if not records:
                    raise ValueError
                record = records[0]
            return self._normalize(record, latitude, longitude, mode)
        except (KeyError, IndexError, TypeError, ValueError, AttributeError):
            raise WeatherProviderError("Weather provider response was invalid.") from None

    @staticmethod
    def _normalize(
        record: dict[str, Any], latitude: float, longitude: float, mode: WeatherMode
    ) -> NormalizedWeather:
        main = record.get("main") or {}
        wind = record.get("wind") or {}
        clouds = record.get("clouds") or {}
        rain = record.get("rain") or {}
    # OpenWeather /forecast reports accumulated rain.3h; use its hourly
        # average to match the training field's one-hour precipitation depth.
        rain_key = "1h" if mode == "current" else "3h"
        rain_factor = 1 / 25.4 if mode == "current" else 1 / (3 * 25.4)
        timestamp = record.get("dt")
        observed_at = (
            datetime.fromtimestamp(float(timestamp), tz=timezone.utc)
            if timestamp is not None
            else None
        )
        return NormalizedWeather(
            air_temperature=_optional_float(main.get("temp")),
            cloud_coverage=(
                float(clouds["all"]) * 9 / 100 if clouds.get("all") is not None else None
            ),
            dew_temperature=_optional_float(main.get("dew_point")),
            precip_depth_1_hr=(
                float(rain[rain_key]) * rain_factor
                if rain.get(rain_key) is not None
                else None
            ),
            # The standard 2.5 endpoint generally returns `pressure`; newer
            # payloads may additionally distinguish `sea_level`. Both are hPa.
            sea_level_pressure=_optional_float(
                main.get("sea_level", main.get("pressure"))
            ),
            wind_direction=_optional_float(wind.get("deg")),
            wind_speed=_optional_float(wind.get("speed")),
            provider="openweather",
            retrieved_at=datetime.now(timezone.utc),
            source_latitude=latitude,
            source_longitude=longitude,
            observation_at=observed_at,
            mode=mode,
        )


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)
