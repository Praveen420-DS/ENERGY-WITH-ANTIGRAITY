const METER_LABELS = {
    0: "Electricity",
    1: "Chilled water",
    2: "Steam",
    3: "Hot water",
};

function PredictionResult({ result, loading, error }) {
    if (loading) {
        return (
            <section className="prediction-result" aria-live="polite">
                <h2>Running production inference</h2>
                <p>The validated model is processing your observation.</p>
            </section>
        );
    }
    if (error) {
        return (
            <section className={`prediction-result error-state ${error.kind}`} role="alert">
                <h2>Prediction unavailable</h2>
                <p>{error.message}</p>
            </section>
        );
    }
    if (!result) {
        return (
            <section className="prediction-result empty-state">
                <h2>No prediction yet</h2>
                <p>Complete the form or load the sample input to begin.</p>
            </section>
        );
    }

    return (
        <section className="prediction-result success-state" aria-live="polite">
            <p className="result-eyebrow">Predicted meter reading</p>
            <p className="result-value">
                {result.predicted_meter_reading.toLocaleString(
                    undefined,
                    { maximumFractionDigits: 4 },
                )}
            </p>
            <p className="unit-note">{result.unit_note}</p>
            <dl className="result-details">
                <div><dt>Meter</dt><dd>{METER_LABELS[result.meter]}</dd></div>
                <div><dt>Model</dt><dd>{result.model_version}</dd></div>
                <div><dt>Input time</dt><dd>{result.input_timestamp}</dd></div>
                <div><dt>Generated</dt><dd>{result.prediction_timestamp}</dd></div>
                <div><dt>Processing</dt><dd>{result.processing_time_ms.toFixed(2)} ms</dd></div>
                <div><dt>Request ID</dt><dd className="request-id">{result.request_id}</dd></div>
            </dl>
            {result.warnings.length > 0 && (
                <div className="prediction-warnings">
                    <h3>Model warnings</h3>
                    <ul>
                        {result.warnings.map((warning) => <li key={warning}>{warning}</li>)}
                    </ul>
                </div>
            )}
        </section>
    );
}

export default PredictionResult;
