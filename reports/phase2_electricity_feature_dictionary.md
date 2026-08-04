# Phase 2 Electricity Feature Dictionary

The electricity unit is not verified; the target is therefore described only as an electricity meter reading or electricity consumption value.

| Feature | Category | Source or formula | Meaning | Expected range | Missing handling | Sent to model | Leakage notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| building_id | identifier | source building_id | Building identifier | observed IDs | not imputed | False | Raw predictor/identifier; no target derivation |
| site_id | identifier | source site_id | Site identifier | 0..15 observed | not imputed | False | Raw predictor/identifier; no target derivation |
| primary_use | categorical | source primary_use | Building use category | observed categories | model-time handling | True | Raw predictor/identifier; no target derivation |
| square_feet | building | source square_feet | Building floor area | >0 when valid | raw missing retained | True | Raw predictor/identifier; no target derivation |
| year_built | building | source year_built | Construction year | 1800..timestamp year when valid | raw missing retained | True | Raw predictor/identifier; no target derivation |
| floor_count | building | source floor_count | Number of floors | >0 when valid | raw missing retained | True | Raw predictor/identifier; no target derivation |
| timestamp | timestamp | source timestamp | Observation timestamp | 2016 observed | must be present | False | Raw predictor/identifier; no target derivation |
| air_temperature | weather | source air_temperature | Air Temperature | source-dependent | indicator + causal carry + frozen training medians | True | Raw predictor/identifier; no target derivation |
| cloud_coverage | weather | source cloud_coverage | Cloud Coverage | source-dependent | indicator + causal carry + frozen training medians | True | Raw predictor/identifier; no target derivation |
| dew_temperature | weather | source dew_temperature | Dew Temperature | source-dependent | indicator + causal carry + frozen training medians | True | Raw predictor/identifier; no target derivation |
| precip_depth_1_hr | weather | source precip_depth_1_hr | Precip Depth 1 Hr | source-dependent | indicator + causal carry + frozen training medians | True | Raw predictor/identifier; no target derivation |
| sea_level_pressure | weather | source sea_level_pressure | Sea Level Pressure | source-dependent | indicator + causal carry + frozen training medians | True | Raw predictor/identifier; no target derivation |
| wind_direction | weather | source wind_direction | Wind Direction | source-dependent | indicator + causal carry + frozen training medians | True | Raw predictor/identifier; no target derivation |
| wind_speed | weather | source wind_speed | Wind Speed | source-dependent | indicator + causal carry + frozen training medians | True | Raw predictor/identifier; no target derivation |
| meter_reading | target | source meter_reading | Electricity meter reading; unit unverified | >=0 | must be present; zero retained | False | Target only; never predictor |
| air_temperature_missing | missing_indicator | 1 when source air_temperature was missing before deterministic weather treatment | Air Temperature Missing | 0..1 | never missing | True | Deterministic predictors only; meter_reading is never read |
| cloud_coverage_missing | missing_indicator | 1 when source cloud_coverage was missing before deterministic weather treatment | Cloud Coverage Missing | 0..1 | never missing | True | Deterministic predictors only; meter_reading is never read |
| dew_temperature_missing | missing_indicator | 1 when source dew_temperature was missing before deterministic weather treatment | Dew Temperature Missing | 0..1 | never missing | True | Deterministic predictors only; meter_reading is never read |
| precip_depth_1_hr_missing | missing_indicator | 1 when source precip_depth_1_hr was missing before deterministic weather treatment | Precip Depth 1 Hr Missing | 0..1 | never missing | True | Deterministic predictors only; meter_reading is never read |
| sea_level_pressure_missing | missing_indicator | 1 when source sea_level_pressure was missing before deterministic weather treatment | Sea Level Pressure Missing | 0..1 | never missing | True | Deterministic predictors only; meter_reading is never read |
| wind_direction_missing | missing_indicator | 1 when source wind_direction was missing before deterministic weather treatment | Wind Direction Missing | 0..1 | never missing | True | Deterministic predictors only; meter_reading is never read |
| wind_speed_missing | missing_indicator | 1 when source wind_speed was missing before deterministic weather treatment | Wind Speed Missing | 0..1 | never missing | True | Deterministic predictors only; meter_reading is never read |
| year | calendar | timestamp calendar year | Year | documented by formula/source | never missing | True | Deterministic predictors only; meter_reading is never read |
| quarter | calendar | timestamp calendar quarter (1..4) | Quarter | documented by formula/source | never missing | True | Deterministic predictors only; meter_reading is never read |
| month | calendar | timestamp calendar month (1..12) | Month | documented by formula/source | never missing | True | Deterministic predictors only; meter_reading is never read |
| week_of_year | calendar | ISO-8601 week number | Week Of Year | documented by formula/source | never missing | True | Deterministic predictors only; meter_reading is never read |
| day | calendar | timestamp day of month | Day | documented by formula/source | never missing | True | Deterministic predictors only; meter_reading is never read |
| day_of_year | calendar | timestamp ordinal day of year | Day Of Year | documented by formula/source | never missing | True | Deterministic predictors only; meter_reading is never read |
| weekday | calendar | Monday=0 through Sunday=6 | Weekday | documented by formula/source | never missing | True | Deterministic predictors only; meter_reading is never read |
| hour | calendar | timestamp hour (0..23) | Hour | documented by formula/source | never missing | True | Deterministic predictors only; meter_reading is never read |
| is_weekend | calendar | 1 when weekday >= 5, otherwise 0 | Is Weekend | 0..1 | never missing | True | Deterministic predictors only; meter_reading is never read |
| season | calendar | winter=Dec-Feb, spring=Mar-May, summer=Jun-Aug, autumn=Sep-Nov | Season | documented by formula/source | never missing | True | Deterministic predictors only; meter_reading is never read |
| hour_sin | cyclical | sin(2*pi*hour/24) | Hour Sin | documented by formula/source | never missing | True | Deterministic predictors only; meter_reading is never read |
| hour_cos | cyclical | cos(2*pi*hour/24) | Hour Cos | documented by formula/source | never missing | True | Deterministic predictors only; meter_reading is never read |
| weekday_sin | cyclical | sin(2*pi*weekday/7) | Weekday Sin | documented by formula/source | never missing | True | Deterministic predictors only; meter_reading is never read |
| weekday_cos | cyclical | cos(2*pi*weekday/7) | Weekday Cos | documented by formula/source | never missing | True | Deterministic predictors only; meter_reading is never read |
| month_sin | cyclical | sin(2*pi*(month-1)/12) | Month Sin | documented by formula/source | never missing | True | Deterministic predictors only; meter_reading is never read |
| month_cos | cyclical | cos(2*pi*(month-1)/12) | Month Cos | documented by formula/source | never missing | True | Deterministic predictors only; meter_reading is never read |
| building_age | building | max(0, timestamp year - year_built); missing when year_built is invalid/missing | Building Age | documented by formula/source | missing if invalid building input | True | Deterministic predictors only; meter_reading is never read |
| log_square_feet | building | log1p(square_feet) only when square_feet > 0; otherwise missing | Log Square Feet | documented by formula/source | missing if invalid building input | True | Deterministic predictors only; meter_reading is never read |
| area_per_floor | building | square_feet/floor_count only when square_feet > 0 and floor_count > 0; otherwise missing | Area Per Floor | documented by formula/source | missing if invalid building input | True | Deterministic predictors only; meter_reading is never read |
| temperature_difference | weather_derived | air_temperature - dew_temperature | Temperature Difference | documented by formula/source | weather inputs deterministically treated first | True | Deterministic predictors only; meter_reading is never read |
| relative_humidity_proxy | weather_derived | 100*exp(17.625*Td/(243.04+Td) - 17.625*T/(243.04+T)), clipped to 0..100; approximation only | Relative Humidity Proxy | documented by formula/source | weather inputs deterministically treated first | True | Deterministic predictors only; meter_reading is never read |
| wind_x | weather_derived | wind_speed*cos(wind_direction*pi/180) | Wind X | documented by formula/source | weather inputs deterministically treated first | True | Deterministic predictors only; meter_reading is never read |
| wind_y | weather_derived | wind_speed*sin(wind_direction*pi/180) | Wind Y | documented by formula/source | weather inputs deterministically treated first | True | Deterministic predictors only; meter_reading is never read |
| temperature_x_square_feet | weather_derived | air_temperature*square_feet when square_feet is valid | Temperature X Square Feet | documented by formula/source | weather inputs deterministically treated first | True | Deterministic predictors only; meter_reading is never read |
| hour_x_temperature | weather_derived | hour*air_temperature | Hour X Temperature | documented by formula/source | weather inputs deterministically treated first | True | Deterministic predictors only; meter_reading is never read |
| cooling_demand_proxy | weather_derived | max(0, air_temperature-18); heuristic 18 C balance point | Cooling Demand Proxy | documented by formula/source | weather inputs deterministically treated first | True | Deterministic predictors only; meter_reading is never read |
| heating_demand_proxy | weather_derived | max(0, 18-air_temperature); heuristic 18 C balance point | Heating Demand Proxy | documented by formula/source | weather inputs deterministically treated first | True | Deterministic predictors only; meter_reading is never read |
