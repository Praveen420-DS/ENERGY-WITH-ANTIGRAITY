import { Activity, ArrowUpRight, Bolt, BrainCircuit, CalendarDays, CheckCircle2, FileBarChart, Lightbulb, Server, Sparkles, UserRound } from "lucide-react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import ChartCard from "../components/ChartCard";
import DataTable from "../components/DataTable";
import PageHeader from "../components/PageHeader";
import StatCard from "../components/StatCard";

const meters = ["Electricity"];
const colors = ["#8b5cf6", "#3b82f6", "#22c55e", "#f59e0b"];
const formatEnergy = (value) => Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 1 });

export default function OverviewPage({ predictions, health, onNavigate }) {
    const total = predictions.length;
    const average = total ? predictions.reduce((sum, item) => sum + Number(item.predicted_kwh || 0), 0) / total : 0;
    const todayKey = new Date().toDateString();
    const today = predictions.filter((item) => new Date(item.predicted_at).toDateString() === todayKey).reduce((sum, item) => sum + Number(item.predicted_kwh || 0), 0);
    const trend = [...predictions].slice(-12).map((item) => ({
        date: new Date(item.predicted_at).toLocaleDateString("en-IN", {
            day: "2-digit",
            month: "short",
            year: "numeric",
        }),
        value: Number(item.predicted_kwh || 0),
    }));

    const distribution = [
        {
            name: "Electricity",
            value: predictions.length,
        },
    ];
    const columns = [
        { key: "id", label: "Prediction ID", render: (row) => <span className="mono">#{row.id}</span> },
        { key: "meter_id", label: "Meter", render: () => "Electricity" },
        { key: "predicted_kwh", label: "Consumption", render: (row) => <strong>{formatEnergy(row.predicted_kwh)} kWh</strong> },
        { key: "predicted_at", label: "Generated", render: (row) => new Date(row.predicted_at).toLocaleString() },
    ];
    return (
        <>
            <PageHeader eyebrow="Overview" title="Energy intelligence dashboard" description="Monitor model activity and consumption forecasts across your energy portfolio." actions={<button className="button button-primary" onClick={() => onNavigate("prediction")}><Bolt size={17} />New prediction</button>} />
            <div className="stats-grid">
                <StatCard title="Total predictions" value={total.toLocaleString()} subtitle="All recorded forecasts" icon={Sparkles} />
                <StatCard title="Average consumption" value={`${formatEnergy(average)} kWh`} subtitle="Across prediction history" icon={Activity} tone="blue" />
                <StatCard title="Today's consumption" value={`${formatEnergy(today)} kWh`} subtitle="Predicted today" icon={CalendarDays} tone="green" />
                <StatCard title="Model status" value={health?.model_loaded ? "Operational" : "Unavailable"} subtitle={health?.model_version || "Version unavailable"} icon={BrainCircuit} tone={health?.model_loaded ? "green" : "orange"} />
            </div>
            <div className="analytics-grid">
                <ChartCard title="Energy trend" subtitle="Recent predicted consumption" className="chart-wide">
                    {trend.length ? <ResponsiveContainer width="100%" height={285}><AreaChart data={trend}><defs><linearGradient id="energyFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.45}/><stop offset="100%" stopColor="#8b5cf6" stopOpacity={0}/></linearGradient></defs><CartesianGrid stroke="#273449" vertical={false}/><XAxis dataKey="date" stroke="#94a3b8" tickLine={false}/><YAxis stroke="#94a3b8" tickLine={false}/><Tooltip contentStyle={{ background: "#111827", border: "1px solid #334155", borderRadius: 10 }}/><Area type="monotone" dataKey="value" stroke="#8b5cf6" strokeWidth={3} fill="url(#energyFill)"/></AreaChart></ResponsiveContainer> : <div className="chart-empty">Trend data appears after predictions are recorded.</div>}
                </ChartCard>
                <ChartCard title="Meter distribution" subtitle="Forecasts by meter type">
                    <ResponsiveContainer width="100%" height={285}><BarChart data={distribution} layout="vertical"><CartesianGrid stroke="#273449" horizontal={false}/><XAxis type="number" stroke="#94a3b8" allowDecimals={false}/><YAxis type="category" dataKey="name" stroke="#94a3b8" width={90} tick={{ fontSize: 11 }}/><Tooltip cursor={{ fill: "#263247" }} contentStyle={{ background: "#111827", border: "1px solid #334155", borderRadius: 10 }}/><Bar dataKey="value" radius={[0, 6, 6, 0]}>{distribution.map((entry, i) => <Cell key={entry.name} fill={colors[i]} />)}</Bar></BarChart></ResponsiveContainer>
                </ChartCard>
            </div>
            <div className="overview-operations">
                <section className="panel system-panel">
                    <div className="panel-heading"><div><h2>System status</h2><p>Live production service health</p></div><span className={`health-pill ${health?.model_loaded ? "online" : "offline"}`}><span className="status-dot" />{health?.model_loaded ? "All systems operational" : "Service attention required"}</span></div>
                    <div className="status-list"><div><span><Server size={17} /></span><div><strong>Prediction API</strong><small>Connected and responding</small></div><CheckCircle2 size={18} /></div><div><span><BrainCircuit size={17} /></span><div><strong>Production model</strong><small>{health?.model_version || "Version unavailable"}</small></div><CheckCircle2 className={health?.model_loaded ? "" : "status-muted"} size={18} /></div></div>
                </section>
                <section className="panel quick-actions-panel">
                    <div className="panel-heading"><div><h2>Quick actions</h2><p>Common workspace tasks</p></div></div>
                    <div className="quick-action-grid"><button onClick={() => onNavigate("prediction")}><span><Bolt size={19} /></span><strong>New forecast</strong><small>Generate an energy prediction</small><ArrowUpRight size={16} /></button><button onClick={() => onNavigate("reports")}><span><FileBarChart size={19} /></span><strong>View reports</strong><small>Explore performance history</small><ArrowUpRight size={16} /></button><button onClick={() => onNavigate("profile")}><span><UserRound size={19} /></span><strong>Account settings</strong><small>Review access and profile</small><ArrowUpRight size={16} /></button></div>
                </section>
            </div>
            <section className="panel recent-panel"><div className="panel-heading"><div><h2>Recent predictions</h2><p>Latest persisted forecasting activity</p></div><button className="text-button" onClick={() => onNavigate("reports")}>View reports <ArrowUpRight size={15}/></button></div><DataTable columns={columns} rows={[...predictions].reverse().slice(0, 6)} emptyTitle="No predictions recorded" emptyDescription="Generate a forecast to start building your analytics history." /></section>
            <section className="recommendation"><span><Lightbulb /></span><div><p className="eyebrow">Energy-saving recommendation</p><h2>Build a baseline before optimizing demand</h2><p>Generate forecasts across representative days. A broader history makes it easier to spot peak-load patterns and prioritize efficiency work.</p></div><button className="button button-secondary" onClick={() => onNavigate("prediction")}>Run analysis</button></section>
        </>
    );
}
