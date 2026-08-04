from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.phase2_electricity_feature_engineering import (
    CATEGORICAL,
    NUMERIC_PREDICTORS,
    OUTPUT_COLUMNS,
    RAW_WEATHER,
    create_features,
    run_pipeline,
    treat_weather_forward_only,
    validate_source_chunk,
)


def source_frame(meter: int = 0) -> pd.DataFrame:
    timestamps = pd.to_datetime([
        "2016-01-01 00:00:00", "2016-01-01 01:00:00",
        "2016-03-05 12:00:00", "2016-07-02 23:00:00",
    ])
    return pd.DataFrame({
        "building_id": [1, 1, 2, 2], "meter": [meter]*4,
        "timestamp": timestamps, "meter_reading": [0.0, 10.0, 20.0, 30.0],
        "site_id": [0, 0, 1, 1], "primary_use": ["Education", "Education", "Office", "Office"],
        "square_feet": [1000.0, 1000.0, np.nan, np.nan],
        "year_built": [2000.0, 2000.0, 2020.0, 2020.0],
        "floor_count": [2.0, 2.0, 0.0, 0.0],
        "air_temperature": [np.nan, 20.0, 25.0, 30.0],
        "cloud_coverage": [np.nan, 2.0, 3.0, 4.0],
        "dew_temperature": [np.nan, 10.0, 15.0, 20.0],
        "precip_depth_1_hr": [np.nan, 0.0, 1.0, 0.0],
        "sea_level_pressure": [np.nan, 1010.0, 1011.0, 1012.0],
        "wind_direction": [np.nan, 90.0, 180.0, 270.0],
        "wind_speed": [np.nan, 2.0, 3.0, 4.0],
    })


def test_meter_zero_validation_and_non_electricity_rejection():
    validate_source_chunk(source_frame())
    with pytest.raises(ValueError, match="Non-electricity"):
        validate_source_chunk(source_frame(meter=1))


def test_calendar_cyclical_season_and_column_order():
    frame = source_frame().fillna({column: 1.0 for column in RAW_WEATHER})
    featured = create_features(frame)
    assert featured.columns.tolist() == OUTPUT_COLUMNS
    assert featured.loc[0, "year"] == 2016
    assert featured.loc[0, "quarter"] == 1
    assert featured.loc[0, "week_of_year"] == 53
    assert featured.loc[0, "weekday"] == 4
    assert featured.loc[0, "season"] == "winter"
    assert featured.loc[2, "season"] == "spring"
    assert featured.loc[3, "season"] == "summer"
    assert featured.loc[0, "hour_sin"] == pytest.approx(0.0, abs=1e-7)
    assert featured.loc[0, "hour_cos"] == pytest.approx(1.0, abs=1e-7)


def test_building_safety_and_no_infinite_values():
    frame = source_frame().fillna({column: 1.0 for column in RAW_WEATHER})
    featured = create_features(frame)
    assert featured.loc[0, "building_age"] == 16
    assert pd.isna(featured.loc[2, "building_age"])
    assert pd.isna(featured.loc[2, "log_square_feet"])
    assert pd.isna(featured.loc[2, "area_per_floor"])
    assert not np.isinf(featured.select_dtypes(include=[np.number]).to_numpy()).any()


def test_target_is_preserved_but_not_used_to_create_predictors():
    first = source_frame().fillna({column: 1.0 for column in RAW_WEATHER})
    second = first.copy(); second["meter_reading"] = [999, 998, 997, 996]
    a, b = create_features(first), create_features(second)
    pd.testing.assert_frame_equal(a.drop(columns="meter_reading"), b.drop(columns="meter_reading"))
    assert a["meter_reading"].tolist() == [0.0, 10.0, 20.0, 30.0]
    assert "meter" not in a.columns


def test_weather_fallback_and_missing_indicators():
    frame = source_frame().iloc[:2].copy().sort_values("timestamp")
    site = {0: {column: 7.0 for column in RAW_WEATHER}}
    global_values = {column: 9.0 for column in RAW_WEATHER}
    treated = treat_weather_forward_only(frame, {}, site, global_values)
    assert treated.loc[0, "air_temperature"] == 7.0
    assert treated.loc[0, "air_temperature_missing"] == 1
    assert treated.loc[1, "air_temperature_missing"] == 0
    assert not treated[RAW_WEATHER].isna().any(axis=None)


def test_chunked_pipeline_schema_zero_preservation_and_overwrite(tmp_path: Path):
    source = source_frame()
    input_path = tmp_path / "input.csv"; output_path = tmp_path / "features.csv"
    reports = tmp_path / "reports"; source.to_csv(input_path, index=False)
    audit = run_pipeline(input_path, output_path, reports, chunk_size=2)
    output = pd.read_csv(output_path)
    assert audit["input_rows"] == audit["output_rows"] == 4
    assert audit["zero_targets_preserved"] == 1
    assert output.columns.tolist() == OUTPUT_COLUMNS
    assert "meter" not in output.columns
    assert not output[RAW_WEATHER].isna().any(axis=None)
    assert not np.isinf(output.select_dtypes(include=[np.number]).to_numpy()).any()
    schema = json.loads((reports / "phase2_electricity_feature_schema.json").read_text())
    assert schema["meter_removed_from_predictors"] is True
    assert schema["target_derived_features"] is False
    assert schema["feature_count"] == len(NUMERIC_PREDICTORS) + len(CATEGORICAL)
    assert (reports / "phase2_electricity_feature_dictionary.md").is_file()
    assert (reports / "phase2_electricity_feature_audit.json").is_file()
    assert (reports / "phase2_electricity_feature_audit.md").is_file()
    with pytest.raises(FileExistsError):
        run_pipeline(input_path, output_path, reports, chunk_size=2)


def test_sample_row_limit(tmp_path: Path):
    input_path = tmp_path / "input.csv"; output_path = tmp_path / "sample.csv"
    source_frame().to_csv(input_path, index=False)
    audit = run_pipeline(input_path, output_path, tmp_path / "reports", chunk_size=2, sample_rows=3)
    assert audit["input_rows"] == audit["output_rows"] == 3
