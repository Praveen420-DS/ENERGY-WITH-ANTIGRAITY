import { useState } from "react";

import PredictionForm, { EMPTY_INPUT } from "../components/PredictionForm";
import PredictionResult from "../components/PredictionResult";
import { predictEnergy } from "../services/api";

const NUMERIC_FIELDS = [
    "building_id", "meter", "site_id", "square_feet", "year_built",
    "floor_count", "air_temperature", "cloud_coverage", "dew_temperature",
    "precip_depth_1_hr", "sea_level_pressure", "wind_direction", "wind_speed",
];

function PredictionPage() {
    const [values, setValues] = useState({ ...EMPTY_INPUT });
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);
    const [fieldErrors, setFieldErrors] = useState({});
    const [loading, setLoading] = useState(false);

    const submit = async (event) => {
        event.preventDefault();
        if (loading) return;
        setLoading(true);
        setError(null);
        setFieldErrors({});
        try {
            const payload = { ...values };
            NUMERIC_FIELDS.forEach((field) => {
                payload[field] = Number(values[field]);
            });
            setResult(await predictEnergy(payload));
        } catch (requestError) {
            setError(requestError);
            setFieldErrors(Object.fromEntries(
                (requestError.details || [])
                    .filter((detail) => detail.field)
                    .map((detail) => [detail.field, detail.message]),
            ));
        } finally {
            setLoading(false);
        }
    };

    const reset = () => {
        setValues({ ...EMPTY_INPUT });
        setResult(null);
        setError(null);
        setFieldErrors({});
    };

    return (
        <div className="prediction-page">
            <header className="prediction-intro">
                <p className="result-eyebrow">Production model</p>
                <h1>Energy consumption prediction</h1>
                <p>
                    Submit raw observations to the validated server-side model.
                    Predictions are informational and are not approved for billing
                    or safety-critical control.
                </p>
            </header>
            <div className="prediction-layout">
                <PredictionForm
                    values={values}
                    setValues={setValues}
                    onSubmit={submit}
                    onReset={reset}
                    loading={loading}
                    fieldErrors={fieldErrors}
                />
                <PredictionResult result={result} loading={loading} error={error} />
            </div>
        </div>
    );
}

export default PredictionPage;
