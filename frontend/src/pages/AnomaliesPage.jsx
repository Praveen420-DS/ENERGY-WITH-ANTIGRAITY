import { useEffect, useState } from "react";
import { detectAnomalies, getAnomalies } from "../services/api";
import DataTable from "../components/DataTable";
import PageHeader from "../components/PageHeader";

export default function AnomaliesPage() {
    const [rows, setRows] = useState([]);
    const [busy, setBusy] = useState(true);
    const [error, setError] = useState("");
    const load = async () => {
        setBusy(true); setError("");
        try { setRows(await getAnomalies()); } catch { setError("Anomaly records could not be loaded."); }
        finally { setBusy(false); }
    };
    useEffect(() => {
        let active = true;
        getAnomalies().then((items) => { if (active) setRows(items); })
            .catch(() => { if (active) setError("Anomaly records could not be loaded."); })
            .finally(() => { if (active) setBusy(false); });
        return () => { active = false; };
    }, []);
    const detect = async () => {
        setBusy(true); setError("");
        try { await detectAnomalies(); await load(); } catch { setError("Detection could not be completed. Check that valid historical energy records are available."); setBusy(false); }
    };
    const columns = [
        { key: "timestamp", label: "Observed at", render: (row) => new Date(row.timestamp).toLocaleString() },
        { key: "meter_id", label: "Meter" }, { key: "anomaly_type", label: "Event" },
        { key: "severity", label: "Severity" },
        { key: "actual_kwh", label: "Observed kWh", render: (row) => Number(row.actual_kwh).toFixed(2) },
        { key: "expected_kwh", label: "Expected kWh", render: (row) => Number(row.expected_kwh).toFixed(2) },
    ];
    return <><PageHeader eyebrow="Operational analytics" title="Historical anomaly review" description="Review unusual consumption detected from valid observed energy records." actions={<button className="button button-primary" onClick={detect} disabled={busy}>Run detection</button>} />{error && <p role="alert">{error}</p>}{busy ? <p>Loading anomaly records…</p> : <section className="panel recent-panel"><DataTable columns={columns} rows={rows} emptyTitle="No anomaly records" emptyDescription="Run detection after valid history is available." /></section>}</>;
}
