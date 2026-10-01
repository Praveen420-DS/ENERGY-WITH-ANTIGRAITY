"""Offline tests for weather settings and OpenWeather normalization."""

from datetime import timezone

import httpx
import pytest
from pydantic import SecretStr

from app.config import Settings
from app.services.weather_provider_service import (
    OpenWeatherProvider,
    WeatherProviderError,
)

SECRET_SENTINEL = "test-weather-secret-do-not-print"


def _settings(**overrides) -> Settings:
    return Settings(
        _env_file=None,
        WEATHER_API_KEY=SECRET_SENTINEL,
        WEATHER_API_URL="https://weather.example/v2.5",
        **overrides,
    )


@pytest.mark.asyncio
async def test_current_weather_normalizes_units_and_request():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "dt": 1_700_000_000,
                "main": {
                    "temp": 20.5,
                    "dew_point": 12.25,
                    "pressure": 1012,
                    "sea_level": 1015.4,
                },
                "clouds": {"all": 50},
                "rain": {"1h": 25.4},
                "wind": {"deg": 271, "speed": 3.6},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        weather = await OpenWeatherProvider(_settings(), client=client).retrieve(
            37.5, -122.2
        )

    assert weather.air_temperature == 20.5  # metric API temperature is Celsius.
    assert weather.dew_temperature == 12.25
    assert weather.sea_level_pressure == 1015.4  # hPa (mbar).
    assert weather.wind_speed == 3.6  # metric API speed is m/s.
    assert weather.wind_direction == 271  # degrees clockwise from north.
    assert weather.cloud_coverage == 4.5  # percent converted to 0–9 oktas.
    assert weather.precip_depth_1_hr == pytest.approx(1.0)  # mm to inches.
    assert weather.provider == "openweather"
    assert weather.observation_at is not None
    assert weather.observation_at.tzinfo == timezone.utc
    assert weather.retrieved_at.tzinfo == timezone.utc
    assert weather.source_latitude == 37.5
    assert weather.source_longitude == -122.2
    request = requests[0]
    assert request.url.path == "/v2.5/weather"
    assert request.url.params["units"] == "metric"
    assert request.url.params["appid"] == SECRET_SENTINEL


@pytest.mark.asyncio
async def test_missing_optional_fields_remain_none():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"main": {"temp": 8}, "wind": {}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        weather = await OpenWeatherProvider(_settings(), client=client).retrieve(
            1, 2
        )
    assert weather.air_temperature == 8
    assert weather.cloud_coverage is None
    assert weather.dew_temperature is None
    assert weather.precip_depth_1_hr is None
    assert weather.sea_level_pressure is None
    assert weather.wind_direction is None
    assert weather.wind_speed is None
    assert weather.observation_at is None


@pytest.mark.asyncio
async def test_standard_pressure_field_is_used_when_sea_level_field_is_absent():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"main": {"pressure": 1008.2}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        weather = await OpenWeatherProvider(_settings(), client=client).retrieve(1, 2)
    assert weather.sea_level_pressure == 1008.2


@pytest.mark.asyncio
async def test_forecast_uses_forecast_endpoint_and_converts_three_hour_rain():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"list": [{"dt": 1_700_000_000, "rain": {"3h": 76.2}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        weather = await OpenWeatherProvider(_settings(), client=client).retrieve(
            1, 2, mode="forecast"
        )
    assert weather.mode == "forecast"
    assert weather.precip_depth_1_hr == pytest.approx(1.0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "handler",
    [
        lambda request: httpx.Response(500, request=request),
        lambda request: (_ for _ in ()).throw(httpx.ReadTimeout(SECRET_SENTINEL)),
    ],
)
async def test_http_and_timeout_errors_hide_secret(handler):
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(WeatherProviderError) as caught:
            await OpenWeatherProvider(_settings(), client=client).retrieve(1, 2)
    assert SECRET_SENTINEL not in str(caught.value)
    assert SECRET_SENTINEL not in repr(caught.value)
    assert caught.value.__cause__ is None


@pytest.mark.asyncio
async def test_httpx_request_log_redacts_query_secret(caplog):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with caplog.at_level("INFO", logger="httpx"):
            await OpenWeatherProvider(_settings(), client=client).retrieve(1, 2)
    assert SECRET_SENTINEL not in caplog.text
    assert "appid=[REDACTED]" in caplog.text


def test_weather_settings_load_values_without_repr_exposing_secret(monkeypatch):
    monkeypatch.setenv("WEATHER_API_KEY", SECRET_SENTINEL)
    monkeypatch.setenv("WEATHER_API_URL", "https://env.example/data/2.5")
    settings = Settings(_env_file=None)
    assert settings.weather_api_key.get_secret_value() == SECRET_SENTINEL
    assert settings.weather_api_url == "https://env.example/data/2.5"
    assert SECRET_SENTINEL not in repr(settings)
    assert SECRET_SENTINEL not in str(settings)


def test_weather_key_uses_secret_type():
    settings = _settings()
    assert isinstance(settings.weather_api_key, SecretStr)
    assert SECRET_SENTINEL not in repr(settings.weather_api_key)
