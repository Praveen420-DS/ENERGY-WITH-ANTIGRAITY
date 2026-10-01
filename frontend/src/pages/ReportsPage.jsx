import { CalendarRange, ChevronLeft, ChevronRight, Download, FileText, Gauge, Layers3, Sigma } from "lucide-react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useMemo, useState } from "react";
import Button from "../components/Button";
import ChartCard from "../components/ChartCard";
import DataTable from "../components/DataTable";
import PageHeader from "../components/PageHeader";
import StatCard from "../components/StatCard";

const meters = ["Electricity"];
export default function ReportsPage({ predictions }) {
    const [meter, setMeter] = useState("all");
    const [start, setStart] = useState("");
    const [end, setEnd] = useState("");
    const [page, setPage] = useState(1);
    const pageSize = 8;
    const filtered = useMemo(() => predictions.filter((item) => {
        const date = new Date(item.predicted_at);
        return (meter === "all" || meter === "0") && (!start || date >= new Date(start)) && (!end || date <= new Date(`${end}T23:59:59`));
    }), [predictions, meter, start, end]);
    const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
    const currentPage = Math.min(page, pageCount);
    const pagedRows = [...filtered].reverse().slice((currentPage - 1) * pageSize, currentPage * pageSize);
    const total = filtered.reduce((sum, item) => sum + Number(item.predicted_kwh || 0), 0);
    const average = filtered.length ? total / filtered.length : 0;
    const exportCsv = () => {
        const headers = ["id", "meter", "actual_kwh", "predicted_kwh", "confidence", "predicted_at", "target_start", "horizon"];

        const csv = [
            headers.join(","),
            ...filtered.map((row) =>
                headers
                    .map((key) =>
                        JSON.stringify(
                            key === "meter"
                                ? "Electricity"
                                : row[key] ?? ""
                        )
                    )
                    .join(",")
            ),
        ].join("\n");

        const link = document.createElement("a");
        link.href = URL.createObjectURL(
            new Blob([csv], { type: "text/csv" })
        );
        link.download = `energy-predictions-${new Date().toISOString().slice(0, 10)}.csv`;
        link.click();
        URL.revokeObjectURL(link.href);
    };
    const chart = filtered.map((row) => ({
        date: new Date(row.predicted_at).toLocaleDateString("en-IN", {
            day: "2-digit",
            month: "short",
            year: "numeric"
        }),
        consumption: Number(row.predicted_kwh || 0)
    }));
    const columns = [
        { key: "id", label: "ID", render: (row) => <span className="mono">#{row.id}</span> },
        { key: "meter_id", label: "Meter", render: () => "Electricity" },
        { key: "actual_kwh", label: "Actual reading", render: (row) => row.actual_kwh == null ? "—" : <strong>{Number(row.actual_kwh).toLocaleString(undefined, { maximumFractionDigits: 2 })} kWh</strong> },
        { key: "predicted_kwh", label: "Predicted energy", render: (row) => <strong>{Number(row.predicted_kwh).toLocaleString(undefined, { maximumFractionDigits: 2 })} kWh</strong> },
        { key: "confidence", label: "Confidence", render: (row) => row.confidence == null ? "—" : `${(Number(row.confidence) * 100).toFixed(0)}%` },
        { key: "predicted_at", label: "Generated", render: (row) => new Date(row.predicted_at).toLocaleString() },
    ];
    return (
        <>
            <PageHeader eyebrow="Analytics" title="Energy reports" description="Filter, review, and export persisted prediction history." actions={<><Button variant="secondary" icon={FileText} disabled title="PDF export requires backend support">Export PDF</Button><Button icon={Download} onClick={exportCsv} disabled={!filtered.length}>Export CSV</Button></>} />
            <section className="panel filter-bar">
                <label><span>From date</span><input type="date" value={start} onChange={(e) => { setStart(e.target.value); setPage(1); }} /></label>
                <label><span>To date</span><input type="date" value={end} onChange={(e) => { setEnd(e.target.value); setPage(1); }} /></label>
                <label><span>Meter type</span><select value={meter} onChange={(e) => { setMeter(e.target.value); setPage(1); }}><option value="all">All meters</option>{meters.map((name, index) => <option value={index} key={name}>{name}</option>)}</select></label>
                <button className="button button-ghost" onClick={() => { setStart(""); setEnd(""); setMeter("all"); setPage(1); }}>Clear filters</button>
            </section>
            <div className="stats-grid reports-stats">
                <StatCard title="Predictions" value={filtered.length.toLocaleString()} subtitle="Matching records" icon={Layers3} />
                <StatCard title="Total forecast" value={`${total.toLocaleString(undefined, { maximumFractionDigits: 1 })} kWh`} subtitle="Filtered period" icon={Sigma} tone="blue" />
                <StatCard title="Average forecast" value={`${average.toLocaleString(undefined, { maximumFractionDigits: 1 })} kWh`} subtitle="Per prediction" icon={Gauge} tone="green" />
                <StatCard title="Date coverage" value={start || end ? "Filtered" : "All time"} subtitle={start && end ? `${start} – ${end}` : "No date restrictions"} icon={CalendarRange} tone="orange" />
            </div>
            <ChartCard title="Forecast trend" subtitle="Predicted energy across the selected period">
                {chart.length ? <ResponsiveContainer width="100%" height={300}><AreaChart data={chart}><defs><linearGradient id="reportFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#3b82f6" stopOpacity={0.4}/><stop offset="100%" stopColor="#3b82f6" stopOpacity={0}/></linearGradient></defs><CartesianGrid stroke="#273449" vertical={false}/><XAxis dataKey="date" stroke="#94a3b8"/><YAxis stroke="#94a3b8"/><Tooltip contentStyle={{ background: "#111827", border: "1px solid #334155", borderRadius: 10 }}/><Area dataKey="consumption" stroke="#3b82f6" strokeWidth={3} fill="url(#reportFill)"/></AreaChart></ResponsiveContainer> : <div className="chart-empty">No forecast data matches these filters.</div>}
            </ChartCard>
            <section className="panel report-table"><div className="panel-heading"><div><h2>Prediction history</h2><p>{filtered.length} matching records</p></div></div><DataTable columns={columns} rows={pagedRows} emptyTitle="No matching predictions" emptyDescription="Try clearing your filters or generate a new prediction." />{filtered.length > 0 && <div className="pagination"><p>Showing {(currentPage - 1) * pageSize + 1}–{Math.min(currentPage * pageSize, filtered.length)} of {filtered.length}</p><div><button className="icon-button" onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={currentPage === 1} aria-label="Previous page"><ChevronLeft size={17} /></button><span>Page {currentPage} of {pageCount}</span><button className="icon-button" onClick={() => setPage((value) => Math.min(pageCount, value + 1))} disabled={currentPage === pageCount} aria-label="Next page"><ChevronRight size={17} /></button></div></div>}</section>
        </>
    );
}
