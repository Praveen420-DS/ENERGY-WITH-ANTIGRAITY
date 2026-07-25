const SAMPLE_INPUT = {
    building_id: "0",
    meter: "0",
    timestamp: "2016-07-15T14:00",
    site_id: "0",
    primary_use: "Education",
    square_feet: "7432",
    year_built: "2008",
    floor_count: "4",
    air_temperature: "25",
    cloud_coverage: "6",
    dew_temperature: "20",
    precip_depth_1_hr: "0",
    sea_level_pressure: "1019.7",
    wind_direction: "180",
    wind_speed: "3.1",
};

const EMPTY_INPUT = Object.fromEntries(
    Object.keys(SAMPLE_INPUT).map((key) => [key, ""]),
);

const NUMBER_FIELDS = [
    ["building_id", "Building ID", "Nonnegative identifier", 0, undefined],
    ["site_id", "Site ID", "Nonnegative identifier", 0, undefined],
    ["square_feet", "Square feet", "Building floor area", 0, undefined],
    ["year_built", "Year built", "Accepted range: 1800–2016", 1800, 2016],
    ["floor_count", "Floor count", "Must be greater than zero", 0.01, undefined],
    ["air_temperature", "Air temperature", "Finite weather reading"],
    ["cloud_coverage", "Cloud coverage", "Finite weather reading"],
    ["dew_temperature", "Dew temperature", "Finite weather reading"],
    ["precip_depth_1_hr", "Hourly precipitation", "Negative sentinels are accepted"],
    ["sea_level_pressure", "Sea-level pressure", "Finite weather reading"],
    ["wind_direction", "Wind direction", "Degrees from 0 to 360", 0, 360],
    ["wind_speed", "Wind speed", "Finite weather reading"],
];

function PredictionForm({
    values,
    setValues,
    onSubmit,
    onReset,
    loading,
    fieldErrors,
}) {
    const update = (event) => {
        const { name, value } = event.target;
        setValues((current) => ({ ...current, [name]: value }));
    };

    return (
        <form className="prediction-form" onSubmit={onSubmit}>
            <div className="prediction-form-heading">
                <div>
                    <h2>Production prediction input</h2>
                    <p>Enter raw building and weather observations.</p>
                </div>
                <button
                    type="button"
                    className="secondary-button"
                    onClick={() => setValues({ ...SAMPLE_INPUT })}
                >
                    Use sample
                </button>
            </div>

            <div className="prediction-grid">
                <label>
                    Meter type <span aria-hidden="true">*</span>
                    <select name="meter" value={values.meter} onChange={update} required>
                        <option value="">Select a meter</option>
                        <option value="0">0 — Electricity</option>
                        <option value="1">1 — Chilled water</option>
                        <option value="2">2 — Steam</option>
                        <option value="3">3 — Hot water</option>
                    </select>
                    <small>Units depend on the selected meter.</small>
                    {fieldErrors.meter && <span className="field-error">{fieldErrors.meter}</span>}
                </label>

                <label>
                    Timestamp <span aria-hidden="true">*</span>
                    <input
                        type="datetime-local"
                        name="timestamp"
                        value={values.timestamp}
                        onChange={update}
                        min="1900-01-01T00:00"
                        max="2100-12-31T23:59"
                        required
                    />
                    <small>Timezone-naive observation time.</small>
                    {fieldErrors.timestamp && <span className="field-error">{fieldErrors.timestamp}</span>}
                </label>

                <label>
                    Primary use <span aria-hidden="true">*</span>
                    <input
                        name="primary_use"
                        value={values.primary_use}
                        onChange={update}
                        placeholder="Education"
                        required
                    />
                    <small>Unknown categories are accepted with a warning.</small>
                    {fieldErrors.primary_use && <span className="field-error">{fieldErrors.primary_use}</span>}
                </label>

                {NUMBER_FIELDS.map(([name, label, help, min, max]) => (
                    <label key={name}>
                        {label} <span aria-hidden="true">*</span>
                        <input
                            type="number"
                            name={name}
                            value={values[name]}
                            onChange={update}
                            min={min}
                            max={max}
                            step={name === "building_id" || name === "site_id" ? "1" : "any"}
                            required
                        />
                        <small>{help}</small>
                        {fieldErrors[name] && <span className="field-error">{fieldErrors[name]}</span>}
                    </label>
                ))}
            </div>

            <div className="prediction-actions">
                <button type="submit" className="primary-button" disabled={loading}>
                    {loading ? "Predicting…" : "Generate prediction"}
                </button>
                <button
                    type="button"
                    className="secondary-button"
                    onClick={onReset}
                    disabled={loading}
                >
                    Reset
                </button>
            </div>
        </form>
    );
}

export { EMPTY_INPUT, SAMPLE_INPUT };
export default PredictionForm;
