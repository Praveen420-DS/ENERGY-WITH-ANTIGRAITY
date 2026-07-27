import { Check, Clipboard, Download, Gauge } from "lucide-react";
import { useState } from "react";
import Button from "./Button";
import EmptyState from "./EmptyState";
import ErrorAlert from "./ErrorAlert";
import LoadingSpinner from "./LoadingSpinner";

const meterLabels = ["Electricity", "Chilled water", "Steam", "Hot water"];
export default function PredictionResult({ result, loading, error }) {
    const [copied, setCopied] = useState(false);
    if (loading) return <section className="prediction-result panel"><LoadingSpinner label="Running production inference" /><p className="result-helper">The validated model is processing this observation.</p></section>;
    if (error) return <section className={`prediction-result panel error-state ${error.kind}`}><ErrorAlert title="Prediction unavailable" message={error.message} /></section>;
    if (!result) return <section className="prediction-result panel"><EmptyState icon={Gauge} title="No prediction yet" description="Complete the form or load the sample input to generate a production prediction." /></section>;
    const download = () => {
        const link = document.createElement("a"); link.href = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], { type: "application/json" })); link.download = `prediction-${result.request_id}.json`; link.click(); URL.revokeObjectURL(link.href);
    };
    const copy = async () => { await navigator.clipboard.writeText(JSON.stringify(result, null, 2)); setCopied(true); window.setTimeout(() => setCopied(false), 1500); };
    return (
        <section className="prediction-result panel success-state" aria-live="polite">
            <div className="result-success"><span><Check /></span><div><strong>Prediction complete</strong><p>Production inference succeeded</p></div></div>
            <p className="eyebrow">Predicted meter reading</p><p className="result-value">{result.predicted_meter_reading.toLocaleString(undefined, { maximumFractionDigits: 4 })}</p><p className="unit-note">{result.unit_note}</p>
            <dl className="result-details"><div><dt>Meter</dt><dd>{meterLabels[result.meter]}</dd></div><div><dt>Model version</dt><dd>{result.model_version}</dd></div><div><dt>Processing time</dt><dd>{result.processing_time_ms.toFixed(2)} ms</dd></div><div><dt>Request ID</dt><dd className="mono">{result.request_id}</dd></div><div><dt>Input time</dt><dd>{new Date(result.input_timestamp).toLocaleString()}</dd></div><div><dt>Generated</dt><dd>{new Date(result.prediction_timestamp).toLocaleString()}</dd></div></dl>
            {result.warnings?.length > 0 && <div className="prediction-warnings"><strong>Model notes</strong><ul>{result.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul></div>}
            <div className="result-actions"><Button variant="secondary" icon={copied ? Check : Clipboard} onClick={copy}>{copied ? "Copied" : "Save result"}</Button><Button variant="ghost" icon={Download} onClick={download}>Download JSON</Button></div>
        </section>
    );
}
