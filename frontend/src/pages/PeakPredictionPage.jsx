import { useState } from "react";
import PageHeader from "../components/PageHeader";
import { predictPeak } from "../services/api";

export default function PeakPredictionPage() {
    const [meterId, setMeterId] = useState("");
    const [result, setResult] = useState(null);
    const [error, setError] = useState("");
    const [busy, setBusy] = useState(false);
    const submit = async (event) => {
        event.preventDefault(); setBusy(true); setError(""); setResult(null);
        try { setResult(await predictPeak({ meter_id: Number(meterId) })); }
        catch { setError("A peak outlook requires at least three valid observed records for this meter."); }
        finally { setBusy(false); }
    };
    return <><PageHeader eyebrow="Demand planning" title="Peak demand outlook" description="Estimate the next consumption interval using a meter’s recent observed history." /><section className="panel recent-panel"><form onSubmit={submit} className="peak-form"><label htmlFor="peak-meter">Meter ID</label><input id="peak-meter" type="number" min="1" required value={meterId} onChange={(event) => setMeterId(event.target.value)} /><button className="button button-primary" disabled={busy}>{busy ? "Calculating…" : "Generate outlook"}</button></form>{error && <p role="alert">{error}</p>}{result && <div className="peak-result" aria-live="polite"><h2>{result.is_peak_likely ? "Peak demand likely" : "Peak demand not indicated"}</h2><p>Forecast: <strong>{Number(result.forecast_kwh).toFixed(2)} kWh</strong></p><p>Historical peak threshold: {Number(result.peak_threshold_kwh).toFixed(2)} kWh</p><p>Based on {result.history_records} valid records.</p></div>}</section></>;
}
