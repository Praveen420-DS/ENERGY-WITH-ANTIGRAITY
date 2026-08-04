# Electricity-Only Dataset Audit

## Executive summary

The original ASHRAE training observations were filtered to `meter == 0`, negative readings were rejected, zero readings were retained, and building metadata plus hourly site weather were merged with validated many-to-one left joins. The result contains **12,060,910 electricity rows**, **1,413 buildings**, and **16 sites**. No model was trained and no original file was modified.

## Output

- Dataset: `data/processed/electricity_processed.csv`
- Format: **CSV**
- Size: **1,069.06 MiB**
- Format decision: PyArrow was unavailable (`ImportError: DLL load failed while importing lib: An Application Control policy has blocked this file.`), so the requested CSV fallback was used.

## Filtering and row counts

| Measure | Count |
| --- | ---: |
| Original training rows scanned | 20,216,100 |
| Original `meter == 0` rows | 12,060,910 |
| Negative readings rejected | 0 |
| Zero readings preserved | 530,169 |
| Final electricity rows | 12,060,910 |
| Unique buildings | 1,413 |
| Unique sites | 16 |

## Date range

- Minimum timestamp: **2016-01-01T00:00:00**
- Maximum timestamp: **2016-12-31T23:00:00**

## Merge quality

| Join | Unmatched output rows |
| --- | ---: |
| Building metadata | 0 |
| Weather | 43,502 |

Unmatched rows are preserved by the left joins and appear as missing metadata or weather values.

## Missing values

| Column | Missing cells | Percent |
| --- | ---: | ---: |
| `building_id` | 0 | 0.0000% |
| `meter` | 0 | 0.0000% |
| `timestamp` | 0 | 0.0000% |
| `meter_reading` | 0 | 0.0000% |
| `site_id` | 0 | 0.0000% |
| `primary_use` | 0 | 0.0000% |
| `square_feet` | 0 | 0.0000% |
| `year_built` | 6,470,035 | 53.6447% |
| `floor_count` | 9,096,083 | 75.4179% |
| `air_temperature` | 47,325 | 0.3924% |
| `cloud_coverage` | 5,329,652 | 44.1895% |
| `dew_temperature` | 49,091 | 0.4070% |
| `precip_depth_1_hr` | 2,513,679 | 20.8415% |
| `sea_level_pressure` | 1,018,383 | 8.4437% |
| `wind_direction` | 678,715 | 5.6274% |
| `wind_speed` | 66,795 | 0.5538% |

## Duplicates

| Measure | Count |
| --- | ---: |
| Duplicate (`building_id`, `meter`, `timestamp`) keys | 0 |
| Duplicate complete rows | 0 |

Duplicate detection used exact pandas 64-bit row hashes across the complete filtered output.

## Numeric statistics

| Column | Non-null count | Mean | Population std. dev. | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| `building_id` | 12,060,910 | 706.648 | 415.233 | 0 | 1448 |
| `meter` | 12,060,910 | 0 | 0 | 0 | 0 |
| `meter_reading` | 12,060,910 | 170.826 | 380.834 | 0 | 79769 |
| `site_id` | 12,060,910 | 6.74996 | 4.94689 | 0 | 15 |
| `square_feet` | 12,060,910 | 92714.3 | 112110 | 283 | 875000 |
| `year_built` | 5,590,875 | 1968.33 | 31.0156 | 1900 | 2017 |
| `floor_count` | 2,964,827 | 3.79808 | 3.36754 | 1 | 26 |
| `air_temperature` | 12,013,585 | 16.0097 | 10.3977 | -28.9 | 47.2 |
| `cloud_coverage` | 6,731,258 | 2.28416 | 2.55348 | 0 | 9 |
| `dew_temperature` | 12,011,819 | 8.33499 | 9.8368 | -35 | 26.1 |
| `precip_depth_1_hr` | 9,547,231 | 0.801528 | 7.71884 | -1 | 343 |
| `sea_level_pressure` | 11,042,527 | 1016.41 | 7.03579 | 968.2 | 1045.5 |
| `wind_direction` | 11,382,195 | 176.36 | 112.877 | 0 | 360 |
| `wind_speed` | 11,994,115 | 3.55932 | 2.31783 | 0 | 19 |

## Integrity and scope

- Output contains only meter code 0: **passed**
- Negative readings remaining: **0**
- Zero readings preserved: **passed**
- Filtered row accounting: **passed**
- Original ASHRAE files modified: **no**
- Production model or manifest modified: **no**
- Model training performed: **no**
