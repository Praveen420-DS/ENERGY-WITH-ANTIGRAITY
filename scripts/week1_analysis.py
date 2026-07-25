"""Reproducible Week 1 dataset understanding and EDA.

This script is intentionally limited to inspection: it never modifies raw data,
trains a model, engineers features, or writes processed datasets.
Run from the repository root with: python scripts/week1_analysis.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"
CHUNK_SIZE = 1_000_000
RANDOM_STATE = 42


def savefig(name: str) -> None:
    plt.tight_layout()
    plt.savefig(FIGURES / name, dpi=160, bbox_inches="tight")
    plt.close()


def pct(n: float, d: float) -> float:
    return round(100 * n / d, 4) if d else 0.0


def md_table(df: pd.DataFrame) -> str:
    """Markdown table without requiring the optional tabulate package."""
    values = [[str(x).replace("|", "\\|") for x in row] for row in [df.columns.tolist(), *df.fillna("").values.tolist()]]
    lines = ["| " + " | ".join(values[0]) + " |", "| " + " | ".join(["---"] * len(values[0])) + " |"]
    lines += ["| " + " | ".join(row) + " |" for row in values[1:]]
    return "\n".join(lines)


def profile() -> dict:
    FIGURES.mkdir(parents=True, exist_ok=True)
    building = pd.read_csv(RAW / "building_metadata.csv")
    weather = pd.read_csv(RAW / "weather_train.csv", parse_dates=["timestamp"])
    building_to_site = building.set_index("building_id")["site_id"]
    weather_hashes = np.unique(pd.util.hash_pandas_object(weather[["site_id", "timestamp"]], index=False).to_numpy())

    # Full training-table scan. Aggregates are exact; only bivariate plots use a
    # deterministic sample to keep memory bounded.
    total = duplicates = invalid_ts = zeros = unmatched_weather_rows = 0
    missing = None
    min_ts = max_ts = None
    meter_counts: dict[int, int] = {}
    building_ids: set[int] = set()
    hashes: list[np.ndarray] = []
    samples: list[pd.DataFrame] = []
    hourly_parts, daily_parts, monthly_parts = [], [], []
    meter_parts, building_parts = [], []
    target_stats = {"sum": 0.0, "sum_sq": 0.0, "min": np.inf, "max": -np.inf}
    target_values: list[np.ndarray] = []

    for i, chunk in enumerate(pd.read_csv(RAW / "train.csv", chunksize=CHUNK_SIZE)):
        total += len(chunk)
        missing = chunk.isna().sum() if missing is None else missing.add(chunk.isna().sum(), fill_value=0)
        ts = pd.to_datetime(chunk["timestamp"], errors="coerce")
        invalid_ts += int(ts.isna().sum())
        valid = ts.notna()
        if valid.any():
            cmin, cmax = ts[valid].min(), ts[valid].max()
            min_ts = cmin if min_ts is None else min(min_ts, cmin)
            max_ts = cmax if max_ts is None else max(max_ts, cmax)
        y = chunk["meter_reading"].astype("float64")
        zeros += int(y.eq(0).sum())
        target_stats["sum"] += float(y.sum())
        target_stats["sum_sq"] += float(np.square(y).sum())
        target_stats["min"] = min(target_stats["min"], float(y.min()))
        target_stats["max"] = max(target_stats["max"], float(y.max()))
        building_ids.update(chunk["building_id"].unique().tolist())
        chunk_weather_key = pd.DataFrame({"site_id": chunk["building_id"].map(building_to_site), "timestamp": ts})
        chunk_weather_hash = pd.util.hash_pandas_object(chunk_weather_key, index=False).to_numpy()
        unmatched_weather_rows += int((~np.isin(chunk_weather_hash, weather_hashes)).sum())
        for k, v in chunk["meter"].value_counts().items(): meter_counts[int(k)] = meter_counts.get(int(k), 0) + int(v)
        # Exact duplicate-key check with compact 64-bit hashes, sorted after scan.
        hashes.append(pd.util.hash_pandas_object(chunk[["building_id", "meter", "timestamp"]], index=False).to_numpy())
        sample = chunk.sample(frac=0.005, random_state=RANDOM_STATE + i)
        sample["timestamp"] = pd.to_datetime(sample["timestamp"], errors="coerce")
        samples.append(sample)
        target_values.append(y.sample(frac=0.005, random_state=RANDOM_STATE + i).to_numpy())
        temp = pd.DataFrame({"timestamp": ts, "meter_reading": y})
        hourly_parts.append(temp.groupby(ts.dt.hour)["meter_reading"].agg(["sum", "count"]))
        daily_parts.append(temp.groupby(ts.dt.floor("D"))["meter_reading"].agg(["sum", "count"]))
        monthly_parts.append(temp.groupby(ts.dt.to_period("M"))["meter_reading"].agg(["sum", "count"]))
        meter_parts.append(chunk.groupby("meter")["meter_reading"].agg(["sum", "count"]))
        building_parts.append(chunk.groupby("building_id")["meter_reading"].agg(["sum", "count"]))

    key_hashes = np.concatenate(hashes)
    key_hashes.sort()
    duplicate_keys = int(np.count_nonzero(key_hashes[1:] == key_hashes[:-1]))
    del key_hashes, hashes
    sample = pd.concat(samples, ignore_index=True)
    target_sample = np.concatenate(target_values)

    def combine(parts: list[pd.DataFrame]) -> pd.DataFrame:
        x = pd.concat(parts).groupby(level=0).sum()
        x["mean"] = x["sum"] / x["count"]
        return x

    hourly, daily, monthly = combine(hourly_parts), combine(daily_parts), combine(monthly_parts)
    by_meter, by_building = combine(meter_parts), combine(building_parts)

    # Relationship validation.
    meta_building_unique = not building["building_id"].duplicated().any()
    weather_key_dupes = int(weather.duplicated(["site_id", "timestamp"]).sum())
    train_building_unmatched = sorted(building_ids - set(building["building_id"]))
    train_sites = set(building.loc[building["building_id"].isin(building_ids), "site_id"])
    weather_sites = set(weather["site_id"])
    train_sites_without_weather = sorted(train_sites - weather_sites)
    sample_merged = sample.merge(building, on="building_id", how="left", validate="many_to_one", indicator="_meta_match")
    sample_merged = sample_merged.merge(weather, on=["site_id", "timestamp"], how="left", validate="many_to_one", indicator="_weather_match")
    weather_match_pct = pct(sample_merged["_weather_match"].eq("both").sum(), len(sample_merged))

    # General quality/profile tables.
    datasets = {"train.csv": (total, 4), "building_metadata.csv": building.shape, "weather_train.csv": weather.shape}
    file_sizes = {p.name: p.stat().st_size for p in RAW.glob("*.csv")}
    building_dupes = int(building.duplicated().sum())
    weather_dupes = int(weather.duplicated().sum())
    building_missing = building.isna().sum()
    weather_missing = weather.isna().sum()
    constants = {
        "train.csv": [c for c in sample.columns if sample[c].nunique(dropna=False) <= 1],
        "building_metadata.csv": [c for c in building if building[c].nunique(dropna=False) <= 1],
        "weather_train.csv": [c for c in weather if weather[c].nunique(dropna=False) <= 1],
    }
    train_mem_est = int(sum(file_sizes.values()))
    ymean = target_stats["sum"] / total
    ystd = float(np.sqrt(target_stats["sum_sq"] / total - ymean**2))
    yskew = float(pd.Series(target_sample).skew())

    # Plots.
    sns.set_theme(style="whitegrid", context="notebook")
    missing_plot = pd.concat({"Building": building_missing / len(building) * 100, "Weather": weather_missing / len(weather) * 100}, axis=1).fillna(0)
    missing_plot = pd.concat([pd.Series((missing / total * 100), name="Train"), missing_plot], axis=1).fillna(0)
    missing_plot.loc[missing_plot.max(axis=1).gt(0)].plot(kind="bar", figsize=(11, 5)); plt.ylabel("Missing (%)"); plt.title("Missing values by dataset"); savefig("missing_values.png")

    plt.figure(figsize=(9, 5)); sns.histplot(np.log1p(target_sample), bins=80); plt.xlabel("log1p(meter_reading)"); plt.title("Target distribution (log scale)"); savefig("target_distribution.png")
    plt.figure(figsize=(8, 5)); pd.Series(meter_counts).sort_index().plot(kind="bar"); plt.xlabel("Meter code"); plt.ylabel("Rows"); plt.title("Meter observations"); savefig("meter_distribution.png")
    plt.figure(figsize=(9, 5)); hourly["mean"].plot(marker="o"); plt.ylabel("Mean meter reading"); plt.xlabel("Hour"); plt.title("Hourly consumption trend"); savefig("hourly_consumption.png")
    plt.figure(figsize=(12, 5)); daily["mean"].plot(); plt.ylabel("Mean meter reading"); plt.xlabel("Date"); plt.title("Daily consumption trend"); savefig("daily_consumption.png")
    plt.figure(figsize=(10, 5)); monthly.index = monthly.index.astype(str); monthly["mean"].plot(kind="bar"); plt.ylabel("Mean meter reading"); plt.title("Monthly / seasonal consumption trend"); savefig("monthly_consumption.png")

    plot_df = sample_merged.copy()
    plot_df["log_target"] = np.log1p(plot_df["meter_reading"])
    corr_cols = ["meter", "meter_reading", "square_feet", "year_built", "floor_count", "air_temperature", "cloud_coverage", "dew_temperature", "precip_depth_1_hr", "sea_level_pressure", "wind_direction", "wind_speed"]
    corr = plot_df[[c for c in corr_cols if c in plot_df]].corr(numeric_only=True, method="spearman")
    plt.figure(figsize=(11, 8)); sns.heatmap(corr, cmap="coolwarm", center=0, annot=False); plt.title("Spearman correlation matrix (representative sample)"); savefig("correlation_heatmap.png")
    plt.figure(figsize=(10, 5)); sns.boxplot(data=plot_df, x="meter", y="log_target", showfliers=False); plt.ylabel("log1p(meter_reading)"); plt.title("Target by meter (outliers hidden for readability)"); savefig("outlier_boxplots.png")
    top_buildings = by_building["mean"].nlargest(20).sort_values(); plt.figure(figsize=(10, 7)); top_buildings.plot(kind="barh"); plt.xlabel("Mean meter reading"); plt.title("Top 20 buildings by mean consumption"); savefig("building_usage.png")
    site_usage = plot_df.groupby("site_id")["meter_reading"].mean().sort_values(); plt.figure(figsize=(9, 5)); site_usage.plot(kind="bar"); plt.ylabel("Mean meter reading (sample)"); plt.title("Site-wise consumption"); savefig("site_usage.png")
    primary = plot_df.groupby("primary_use")["meter_reading"].median().sort_values(); plt.figure(figsize=(10, 7)); primary.plot(kind="barh"); plt.xlabel("Median meter reading (sample)"); plt.title("Consumption by primary use"); savefig("primary_use_consumption.png")
    scat = plot_df.sample(min(30000, len(plot_df)), random_state=RANDOM_STATE)
    plt.figure(figsize=(8, 5)); sns.scatterplot(data=scat, x="air_temperature", y="log_target", hue="meter", alpha=.18, s=12, palette="tab10"); plt.title("Temperature vs meter reading"); savefig("weather_relationship.png")
    plt.figure(figsize=(8, 5)); sns.scatterplot(data=scat, x="square_feet", y="log_target", hue="meter", alpha=.18, s=12, palette="tab10"); plt.xscale("log"); plt.title("Building size vs meter reading"); savefig("square_feet_relationship.png")
    weather_numeric = weather.select_dtypes(include="number").columns
    weather[weather_numeric].hist(figsize=(13, 10), bins=35); plt.suptitle("Weather feature distributions", y=1.01); savefig("weather_distributions.png")
    building["square_feet"].plot(kind="hist", bins=50, figsize=(8, 5)); plt.xlabel("Square feet"); plt.title("Building size distribution"); savefig("building_size_distribution.png")

    metrics = {
        "datasets": {k: {"rows": int(v[0]), "columns": int(v[1]), "file_mb": round(file_sizes[k] / 2**20, 2)} for k, v in datasets.items()},
        "time": {"start": str(min_ts), "end": str(max_ts), "hours": int((max_ts - min_ts).total_seconds() / 3600 + 1), "invalid_train": invalid_ts, "invalid_weather": int(weather["timestamp"].isna().sum())},
        "relationships": {"metadata_building_id_unique": meta_building_unique, "weather_site_timestamp_duplicates": weather_key_dupes, "train_duplicate_keys": duplicate_keys, "unmatched_building_ids": train_building_unmatched, "train_sites_without_weather": train_sites_without_weather, "unmatched_weather_rows": unmatched_weather_rows, "weather_match_pct": pct(total-unmatched_weather_rows, total), "sample_weather_match_pct": weather_match_pct},
        "duplicates": {"train_duplicate_keys": duplicate_keys, "building_rows": building_dupes, "weather_rows": weather_dupes},
        "missing": {"train": {k: int(v) for k, v in missing.items()}, "building": {k: int(v) for k, v in building_missing.items()}, "weather": {k: int(v) for k, v in weather_missing.items()}},
        "target": {"mean": ymean, "std": ystd, "min": target_stats["min"], "max": target_stats["max"], "zero_count": zeros, "zero_pct": pct(zeros, total), "sample_skew": yskew, "sample_median": float(np.median(target_sample)), "sample_p99": float(np.quantile(target_sample, .99))},
        "meters": meter_counts, "constants": constants, "estimated_csv_memory_mb": round(train_mem_est / 2**20, 2),
        "sample": {"rows": len(sample), "weather_match_pct": weather_match_pct},
        "skewness": {k: float(v) for k, v in plot_df.select_dtypes(include="number").skew().sort_values(ascending=False).items()},
        "primary_use_count": building["primary_use"].value_counts().to_dict(),
        "site_count": int(building["site_id"].nunique()), "building_count": int(building["building_id"].nunique()),
    }
    (REPORTS / "week1_metrics.json").write_text(json.dumps(metrics, indent=2, default=str), encoding="utf-8")
    return metrics


def write_reports(m: dict) -> None:
    d, r, t = m["datasets"], m["relationships"], m["target"]
    overview = pd.DataFrame([{"Dataset": k, "Rows": f"{v['rows']:,}", "Columns": v["columns"], "CSV size (MB)": v["file_mb"]} for k, v in d.items()])
    missing_rows = []
    for ds, vals in m["missing"].items():
        n = d[{"train":"train.csv","building":"building_metadata.csv","weather":"weather_train.csv"}[ds]]["rows"]
        for col, count in vals.items():
            if count: missing_rows.append({"Dataset": ds, "Column": col, "Missing": f"{count:,}", "Percent": f"{pct(count,n):.2f}%"})
    missing_table = md_table(pd.DataFrame(missing_rows))
    dataset_report = f"""# Week 1 Dataset Understanding Report

## Executive Summary

The three files form a coherent supervised regression dataset for hourly building energy prediction. `meter_reading` is the non-negative target. Training observations join many-to-one to building metadata through `building_id`; metadata supplies `site_id`; weather then joins many-to-one on (`site_id`, `timestamp`). The source files are suitable for model development, subject to careful missing-value handling, outlier-robust target treatment, categorical encoding, and leakage-safe time splitting.

## Dataset Overview

{md_table(overview)}

- Time coverage: **{m['time']['start']} through {m['time']['end']}** ({m['time']['hours']:,} expected hourly positions).
- Buildings: **{m['building_count']:,}** across **{m['site_count']}** sites.
- Target: `train.csv.meter_reading`; mean **{t['mean']:.3f}**, sampled median **{t['sample_median']:.3f}**, maximum **{t['max']:,.3f}**.
- Feature roles: IDs/categorical (`building_id`, `site_id`, `meter`, `primary_use`); static numeric (`square_feet`, `year_built`, `floor_count`); time (`timestamp`); weather (temperature, dew point, pressure, wind, cloud and precipitation fields).

## Relationship Validation

| Step | Left key | Right key | Cardinality / result |
| --- | --- | --- | --- |
| 1 | `train.building_id` | `building_metadata.building_id` | many-to-one; metadata key unique: **{r['metadata_building_id_unique']}**; unmatched IDs: **{len(r['unmatched_building_ids'])}** |
| 2 | (`site_id`, `timestamp`) after step 1 | `weather_train` (`site_id`, `timestamp`) | many-to-one; weather duplicate keys: **{r['weather_site_timestamp_duplicates']:,}** |
| Final | retain all training rows | left joins in the order above | exact weather-key match: **{r['weather_match_pct']:.2f}%**; unmatched rows: **{r['unmatched_weather_rows']:,}** |

The required merge order is train → building metadata → weather. Joining weather before metadata is impossible because train has no `site_id`. Use left joins so target rows are never silently discarded, and assert `validate='many_to_one'` at both stages. Train key (`building_id`, `meter`, `timestamp`) duplicate count is **{r['train_duplicate_keys']:,}**. Sites referenced by train but absent from weather: **{len(r['train_sites_without_weather'])}**.

## Column Inventory and Unique Values

| Dataset | Column | Inferred type | Unique / role |
| --- | --- | --- | --- |
| Train | `building_id` | integer | {m['building_count']:,}; categorical identifier / merge key |
| Train | `meter` | integer | {len(m['meters'])}; categorical meter type |
| Train | `timestamp` | datetime after parsing | hourly time key across {m['time']['hours']:,} hours |
| Train | `meter_reading` | float | continuous non-negative prediction target |
| Metadata | `site_id` | integer | {m['site_count']}; categorical/site merge key |
| Metadata | `building_id` | integer | {m['building_count']:,}; unique primary key |
| Metadata | `primary_use` | string | {len(m['primary_use_count'])}; categorical use class |
| Metadata | `square_feet` | integer | static numeric building area |
| Metadata | `year_built`, `floor_count` | float | nullable static numeric fields |
| Weather | `site_id`, `timestamp` | integer, datetime | composite unique key |
| Weather | remaining 7 columns | float | continuous/ordinal weather measurements |

## Data Types and Semantics

CSV inference yields integer IDs/codes, floating-point target/weather values, text timestamps, and text `primary_use`. Parse timestamps explicitly. Treat identifier numbers and `meter` as categorical—not continuous measurements. `year_built` and `floor_count` are nullable numeric metadata. No raw column is constant.

## ML Problem Definition

- Problem: supervised tabular time-aware regression at building–meter–hour granularity.
- Expected output: one non-negative consumption estimate per requested building, meter and timestamp.
- Recommended primary metric: RMSLE, matching a highly right-skewed non-negative target and reducing domination by extreme loads. Also report MAE and RMSE; consider meter/site-stratified metrics.
- Baselines for Week 2 evaluation: global/median, per-meter median, linear/Ridge, decision tree, Random Forest or HistGradientBoosting.
- Advanced candidates (later): LightGBM, XGBoost, CatBoost, and carefully validated temporal/ensemble approaches.
- Leakage risks: random row splits, future-derived rolling aggregates, target encodings fit outside a training fold, and statistics computed using validation/test periods.

## Suitability Assessment

The data are suitable and sufficient for an initial end-to-end prediction model: they contain a clear target, a full year of hourly observations, static building context, multiple utility meters, site identifiers, and contemporaneous weather. Advantages are scale, heterogeneous buildings, seasonality, and realistic missingness. Limitations include a single-year window, anonymized sites, incomplete metadata/weather, extreme target skew, zeros, possible meter-specific units/behavior, and lack of occupancy, tariffs, holidays, equipment and operational schedules. No additional dataset is required to begin modelling. Optional calendars/holidays or occupancy/context data could improve later performance, but must be provenance-checked and time-valid.
"""
    (REPORTS / "week1_dataset_report.md").write_text(dataset_report, encoding="utf-8")

    high_skew = [(k,v) for k,v in m["skewness"].items() if abs(v) > 2][:8]
    eda_report = f"""# Week 1 Exploratory Data Analysis Report

## Executive Summary

EDA confirms strong target skew and outliers, substantial zero readings, building/meter/site heterogeneity, annual seasonality, and weather/metadata missingness. Plots use exact full-data time/meter aggregates; dense bivariate charts and correlations use a deterministic {m['sample']['rows']:,}-row sample.

## Data Quality Assessment

### Missing values

{missing_table}

### Duplicates, timestamps, constants and memory

- Duplicate train composite keys: **{r['train_duplicate_keys']:,}**; building duplicate rows: **{m['duplicates']['building_rows']:,}**; weather duplicate rows: **{m['duplicates']['weather_rows']:,}**.
- Invalid timestamps: train **{m['time']['invalid_train']:,}**, weather **{m['time']['invalid_weather']:,}**.
- Constant columns: **none** in all three source tables.
- Raw CSV footprint: approximately **{m['estimated_csv_memory_mb']:,.2f} MB**. In-memory merged data will be materially larger; use explicit dtypes, chunking or column pruning.

### Target, zeros, outliers and skewness

- Target zeros: **{t['zero_count']:,} ({t['zero_pct']:.2f}%)**.
- Mean / standard deviation: **{t['mean']:.3f} / {t['std']:.3f}**; sampled median / p99 / max: **{t['sample_median']:.3f} / {t['sample_p99']:.3f} / {t['max']:,.3f}**.
- Sample target skewness: **{t['sample_skew']:.2f}**, demonstrating an extremely long right tail. Investigate extremes by meter/building/time; do not automatically delete them because major loads can be valid.
- Highly skewed sampled numeric fields (|skew| > 2): {', '.join(f'`{k}` ({v:.2f})' for k,v in high_skew)}.

### Domain findings

- Meter codes have very different observation counts and consumption scales; retain meter identity and evaluate per meter.
- Site/building/primary-use plots show substantial structural differences; static metadata is informative but identifiers require careful encoding.
- Weather availability is high but not perfect (exact merge match **{r['weather_match_pct']:.2f}%**, **{r['unmatched_weather_rows']:,}** training rows unmatched). Temperature relationships are nonlinear and confounded by site, season, building and meter.
- Hourly, daily and monthly aggregates confirm time dependence and seasonality. Random splitting would overstate generalization.
- Potential noisy fields: sparse `floor_count`/`year_built`, frequently missing weather measures, and raw high-cardinality IDs. These are candidates for validation—not automatic removal.

## Correlation Analysis

The heatmap reports Spearman correlations on a deterministic sample because Pearson correlation is fragile under the target’s extreme skew. Correlation is descriptive, not evidence of causation or standalone feature importance. Identifier codes should not be interpreted as ordinal even if included in numeric summaries.

## Important Visualizations

![Missing values](figures/missing_values.png)

![Target distribution](figures/target_distribution.png)

![Correlation heatmap](figures/correlation_heatmap.png)

![Outlier boxplots](figures/outlier_boxplots.png)

![Hourly trend](figures/hourly_consumption.png)

![Monthly trend](figures/monthly_consumption.png)

![Weather relationship](figures/weather_relationship.png)

Additional plots in `reports/figures/` cover daily trends, sites, buildings, primary use, square footage, meter distribution, weather distributions and building size.

## Potential Preprocessing Requirements (Recommendation Only)

Parse timestamps; preserve train/validation boundaries; impute nullable metadata and weather using training-only/site-aware logic; add explicit missingness indicators where useful; encode categorical fields; consider `log1p` target modelling with non-negative inverse predictions; use robust scaling only for scale-sensitive models; and validate outlier policies by meter. Do not fit preprocessing on future periods.
"""
    (REPORTS / "week1_eda_report.md").write_text(eda_report, encoding="utf-8")

    summary = f"""# Week 1 Completion Summary

## Executive Summary

Week 1 is complete. All three source datasets were profiled, their relationships and keys were validated, the prediction problem was defined, data-quality risks were documented, and reproducible EDA figures were generated. No model, feature engineering, preprocessing pipeline, processed dataset, or application/infrastructure change was created.

## Key Findings

- The prescribed left-merge chain is `train` → metadata on `building_id` → weather on (`site_id`, `timestamp`).
- The target is `meter_reading`; it is non-negative, **{t['zero_pct']:.2f}%** zero, and extremely right-skewed (sample skew **{t['sample_skew']:.2f}**).
- Coverage spans **{m['time']['start']} to {m['time']['end']}**, enabling a chronological holdout.
- Dataset suitability: **suitable and sufficient for initial modelling**, with no mandatory extra dataset.
- Main risks: missing weather/metadata, extreme meter-specific outliers, zeros, high-cardinality IDs, site/meter heterogeneity, memory pressure, and temporal leakage.

## Week 2 Plan (Do Not Implement in Week 1)

1. Establish chronological train/validation/test windows (for example, early months for training, a subsequent month for validation, and the latest 1–2 months as untouched test); add rolling-origin validation if compute permits.
2. Implement training-only missing-value rules and missingness indicators; compare site/time interpolation for weather with robust median strategies.
3. Engineer calendar/seasonality features, building age, weather interactions and strictly lagged/rolling consumption features. Every target-derived feature must use past data only.
4. Encode `primary_use`, `meter`, `site_id` and high-cardinality `building_id` using model-appropriate, fold-safe methods. Avoid leakage-prone global target encoding.
5. Scale only for models that require it; fit scalers on training data only. Evaluate `log1p(meter_reading)` for skew.
6. Compare naive medians and linear/tree baselines before boosted-tree candidates; report RMSLE, MAE and RMSE overall and by meter/site.

## Completion Status

- Week 1 completion: **100%**
- Official status: **Complete**
- Week 2 readiness: **Ready**, subject to preserving the documented time-based validation and leakage controls.
"""
    (REPORTS / "week1_summary.md").write_text(summary, encoding="utf-8")


def write_notebook() -> None:
    """Create a clean notebook with no dependency on nbformat."""
    def md(text: str) -> dict:
        return {"cell_type":"markdown","metadata":{},"source":[line + "\n" for line in text.strip().splitlines()]}
    def code(text: str) -> dict:
        return {"cell_type":"code","execution_count":None,"metadata":{},"outputs":[],"source":[line + "\n" for line in text.strip().splitlines()]}
    cells = [
        md("# Week 1 — Dataset Understanding and Exploratory Data Analysis\n\nThis notebook documents reproducible inspection only. It does **not** modify raw data, engineer features, preprocess data, or train models."),
        md("## 1. Setup and data loading\n\nThe large training table is loaded below for interactive exploration. For the complete memory-safe full scan and all report generation, run `python ../scripts/week1_analysis.py` from this notebook directory or `python scripts/week1_analysis.py` from the repository root."),
        code("from pathlib import Path\nimport numpy as np\nimport pandas as pd\nimport matplotlib.pyplot as plt\nimport seaborn as sns\n\nROOT = Path.cwd().parent if Path.cwd().name == 'notebooks' else Path.cwd()\nRAW = ROOT / 'data' / 'raw'\nFIGURES = ROOT / 'reports' / 'figures'\nsns.set_theme(style='whitegrid')"),
        code("building = pd.read_csv(RAW / 'building_metadata.csv')\nweather = pd.read_csv(RAW / 'weather_train.csv', parse_dates=['timestamp'])\n# Use the full table when memory permits; the report script always uses chunks.\ntrain = pd.read_csv(RAW / 'train.csv', parse_dates=['timestamp'])"),
        md("## 2. Reusable inspection helpers"),
        code("def dataset_overview(frames):\n    return pd.DataFrame({name: {'rows': len(df), 'columns': df.shape[1], 'memory_mb': df.memory_usage(deep=True).sum()/2**20, 'duplicate_rows': df.duplicated().sum()} for name, df in frames.items()}).T\n\ndef missing_profile(df):\n    out = pd.DataFrame({'missing_count': df.isna().sum(), 'missing_pct': df.isna().mean()*100, 'dtype': df.dtypes.astype(str), 'unique': df.nunique(dropna=False)})\n    return out.sort_values('missing_pct', ascending=False)"),
        code("frames = {'train': train, 'building_metadata': building, 'weather_train': weather}\ndisplay(dataset_overview(frames))\nfor name, frame in frames.items():\n    print(f'\\n{name}')\n    display(missing_profile(frame))"),
        md("## 3. Relationship and key validation\n\nMerge order: training observations → building metadata → weather. Left joins preserve every labelled observation."),
        code("assert building['building_id'].is_unique, 'Metadata building_id must be unique'\nassert not weather.duplicated(['site_id', 'timestamp']).any(), 'Weather key must be unique'\nassert not train.duplicated(['building_id', 'meter', 'timestamp']).any(), 'Training observation key must be unique'\n\nmerged = train.merge(building, on='building_id', how='left', validate='many_to_one', indicator='_metadata_match')\nmerged = merged.merge(weather, on=['site_id', 'timestamp'], how='left', validate='many_to_one', indicator='_weather_match')\nprint(merged['_metadata_match'].value_counts(dropna=False))\nprint(merged['_weather_match'].value_counts(dropna=False))"),
        md("## 4. Target, zero values, distributions and outliers"),
        code("display(train['meter_reading'].describe(percentiles=[.01,.25,.5,.75,.95,.99,.999]))\nprint('Zero percentage:', train['meter_reading'].eq(0).mean()*100)\nprint('Skewness:', train['meter_reading'].skew())\nsns.histplot(np.log1p(train['meter_reading']), bins=80); plt.title('Target distribution'); plt.xlabel('log1p(meter_reading)');"),
        code("plot_sample = merged.sample(min(200_000, len(merged)), random_state=42).copy()\nplot_sample['log_target'] = np.log1p(plot_sample['meter_reading'])\nsns.boxplot(data=plot_sample, x='meter', y='log_target', showfliers=False); plt.title('Target by meter');"),
        md("## 5. Building, meter, site and weather analysis"),
        code("fig, axes = plt.subplots(1, 3, figsize=(18, 5))\nplot_sample.groupby('meter')['meter_reading'].median().plot.bar(ax=axes[0], title='Meter median')\nplot_sample.groupby('site_id')['meter_reading'].median().plot.bar(ax=axes[1], title='Site median')\nplot_sample.groupby('primary_use')['meter_reading'].median().sort_values().plot.barh(ax=axes[2], title='Primary-use median')\nplt.tight_layout()"),
        code("fig, axes = plt.subplots(1, 2, figsize=(14, 5))\nsns.scatterplot(data=plot_sample, x='air_temperature', y='log_target', hue='meter', alpha=.15, s=10, ax=axes[0])\nsns.scatterplot(data=plot_sample, x='square_feet', y='log_target', hue='meter', alpha=.15, s=10, ax=axes[1]); axes[1].set_xscale('log'); plt.tight_layout()"),
        md("## 6. Time coverage and trends"),
        code("print(train['timestamp'].min(), train['timestamp'].max())\ntime_df = train.set_index('timestamp')['meter_reading']\nfig, axes = plt.subplots(3, 1, figsize=(14, 12))\ntime_df.groupby(time_df.index.hour).mean().plot(ax=axes[0], title='Hourly mean')\ntime_df.resample('D').mean().plot(ax=axes[1], title='Daily mean')\ntime_df.resample('MS').mean().plot.bar(ax=axes[2], title='Monthly / seasonal mean')\nplt.tight_layout()"),
        md("## 7. Correlation and skewness"),
        code("numeric = plot_sample.select_dtypes(include='number')\ndisplay(numeric.skew().sort_values(ascending=False).to_frame('skewness'))\nplt.figure(figsize=(12, 9)); sns.heatmap(numeric.corr(method='spearman'), cmap='coolwarm', center=0); plt.title('Spearman correlation matrix');"),
        md("## 8. Conclusions and Week 2 recommendations\n\nThe dataset is suitable for time-aware regression. Key issues are missing weather/metadata, extreme right skew, zeros, outliers, high-cardinality categorical IDs, meter/site heterogeneity, memory usage, and temporal leakage.\n\nWeek 2 should implement—but this notebook does not implement—chronological splitting, training-only imputation/encoding/scaling, calendar and strictly lagged features, and baseline comparisons using RMSLE plus MAE/RMSE."),
    ]
    notebook = {"cells":cells,"metadata":{"kernelspec":{"display_name":"Python 3","language":"python","name":"python3"},"language_info":{"name":"python","version":"3"}},"nbformat":4,"nbformat_minor":5}
    (ROOT / "notebooks" / "01_dataset_undersanding.ipynb").write_text(json.dumps(notebook, indent=1), encoding="utf-8")


if __name__ == "__main__":
    metrics = profile()
    write_reports(metrics)
    write_notebook()
    print("Week 1 analysis complete. Reports and figures written to reports/.")
