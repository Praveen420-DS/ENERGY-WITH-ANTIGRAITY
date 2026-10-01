import { Building2, CalendarDays, Clock3, Gauge, RotateCcw, Sparkles, WandSparkles } from "lucide-react";
import { useState } from "react";
import Button from "./Button";
import FormField from "./FormField";

const BUILDINGS = [
    { id: "0", name: "North Campus · Education", site_id: "0", primary_use: "Education", square_feet: "7432", year_built: "2008", floor_count: "4" },
    { id: "1", name: "Central Office · Commercial", site_id: "0", primary_use: "Office", square_feet: "125000", year_built: "1998", floor_count: "12" },
    { id: "2", name: "West Medical Center · Healthcare", site_id: "1", primary_use: "Healthcare", square_feet: "86000", year_built: "2005", floor_count: "7" },
    { id: "3", name: "South Distribution Hub · Warehouse", site_id: "2", primary_use: "Warehouse/storage", square_feet: "210000", year_built: "2012", floor_count: "2" },
];
const WEATHER_DEFAULTS = { air_temperature: "25", cloud_coverage: "6", dew_temperature: "20", precip_depth_1_hr: "0", sea_level_pressure: "1019.7", wind_direction: "180", wind_speed: "3.1" };
const EMPTY_INPUT = { building_id: "", meter: "", actual_kwh: "", timestamp: "", site_id: "0", primary_use: "Education", square_feet: "7432", year_built: "2008", floor_count: "4", ...WEATHER_DEFAULTS };
const SAMPLE_INPUT = { ...EMPTY_INPUT, building_id: "0", meter: "0", actual_kwh: "174.3", timestamp: "2016-07-15T14:00" };

export default function PredictionForm({ values, setValues, onSubmit, onReset, loading, fieldErrors }) {
    const [forecastPeriod, setForecastPeriod] = useState("24");
    const update = ({ target: { name, value } }) => setValues((current) => ({ ...current, [name]: value }));
    const selectBuilding = ({ target: { value } }) => {
        const building = BUILDINGS.find((item) => item.id === value);
        setValues((current) => building ? { ...current, building_id: value, site_id: building.site_id, primary_use: building.primary_use, square_feet: building.square_feet, year_built: building.year_built, floor_count: building.floor_count } : { ...current, building_id: "" });
    };
    const reset = () => { setForecastPeriod("24"); onReset(); };
    return (
        <form className="prediction-form panel" onSubmit={onSubmit}>
            <div className="panel-heading form-heading"><div><p className="eyebrow">Forecast configuration</p><h2>Business inputs</h2><p>Select the asset and forecast context. Weather and technical model features are managed automatically.</p></div><Button type="button" variant="secondary" icon={WandSparkles} onClick={() => { setValues({ ...SAMPLE_INPUT }); setForecastPeriod("24"); }}>Use sample</Button></div>
            <div className="business-form-grid">
                <FormField name="building_id" label="Building" hint="Managed property in your portfolio" error={fieldErrors.building_id} required><div className="select-with-icon"><Building2 /><select id="building_id" name="building_id" value={values.building_id} onChange={selectBuilding} required><option value="">Select a building</option>{BUILDINGS.map((building) => <option key={building.id} value={building.id}>{building.name}</option>)}</select></div></FormField>
                <FormField name="meter" label="Meter" hint="Energy stream to forecast" error={fieldErrors.meter} required><div className="select-with-icon"><Gauge /><select id="meter" name="meter" value={values.meter} onChange={update} required><option value="">Select a meter</option><option value="0">Electricity</option><option value="1">Chilled water</option><option value="2">Steam</option><option value="3">Hot water</option></select></div></FormField>
                <FormField name="actual_kwh" label="Current meter reading" unit="kWh" hint="Enter the latest actual electricity consumption reading." error={fieldErrors.actual_kwh} required><div className="input-with-leading-icon"><Gauge /><input id="actual_kwh" type="number" name="actual_kwh" value={values.actual_kwh} onChange={update} min="0" step="any" required /></div></FormField>
                <FormField name="timestamp" label="Prediction date" hint="Starting date and time" error={fieldErrors.timestamp} required><div className="input-with-leading-icon"><CalendarDays /><input id="timestamp" type="datetime-local" name="timestamp" value={values.timestamp} onChange={update} min="1900-01-01T00:00" max="2100-12-31T23:59" required /></div></FormField>
                <FormField name="forecast-period" label="Forecast period" hint="Planning horizon for this analysis"><div className="select-with-icon"><Clock3 /><select id="forecast-period" value={forecastPeriod} onChange={(event) => setForecastPeriod(event.target.value)}><option value="24">Next 24 hours</option><option value="168">Next 7 days</option><option value="720">Next 30 days</option></select></div></FormField>
            </div>
            <div className="managed-features"><span><Sparkles size={17} /></span><div><strong>Advanced features managed automatically</strong><p>Weather observations and building characteristics are securely mapped to the production model.</p></div></div>
            <div className="prediction-actions"><Button type="submit" loading={loading} icon={Sparkles}>Generate forecast</Button><Button type="button" variant="ghost" icon={RotateCcw} onClick={reset} disabled={loading}>Reset</Button></div>
        </form>
    );
}
export { BUILDINGS, EMPTY_INPUT, SAMPLE_INPUT };
