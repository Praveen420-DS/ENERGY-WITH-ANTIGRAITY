import { useCallback, useEffect, useState } from "react";
import ErrorAlert from "../components/ErrorAlert";
import LoadingSpinner from "../components/LoadingSpinner";
import Navbar from "../components/Navbar";
import Sidebar from "../components/Sidebar";
import { getCurrentUser, getModelHealth, getPredictions } from "../services/api";
import OverviewPage from "./OverviewPage";
import PredictionPage from "./PredictionPage";
import ProfilePage from "./ProfilePage";
import ReportsPage from "./ReportsPage";
import AnomaliesPage from "./AnomaliesPage";
import PeakPredictionPage from "./PeakPredictionPage";

export default function Dashboard({ onLogout }) {
    const [activePage, setActivePage] = useState("overview");
    const [sidebarOpen, setSidebarOpen] = useState(false);
    const [user, setUser] = useState(null);
    const [predictions, setPredictions] = useState([]);
    const [health, setHealth] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const loadData = useCallback(async () => {
        setLoading(true); setError("");
        const [userResult, predictionsResult, healthResult] = await Promise.allSettled([getCurrentUser(), getPredictions(), getModelHealth()]);
        if (userResult.status === "fulfilled") setUser(userResult.value);
        if (predictionsResult.status === "fulfilled") setPredictions(predictionsResult.value || []);
        if (healthResult.status === "fulfilled") setHealth(healthResult.value);
        if (userResult.status === "rejected" || predictionsResult.status === "rejected") setError("Some dashboard data could not be loaded. You can still create a prediction.");
        setLoading(false);
    }, []);
    useEffect(() => {
        const timer = window.setTimeout(loadData, 0);
        return () => window.clearTimeout(timer);
    }, [loadData]);
    return (
        <div className="app-shell">
            <Sidebar activePage={activePage} setActivePage={setActivePage} open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
            <div className="workspace">
                <Navbar onLogout={onLogout} user={user} onMenu={() => setSidebarOpen(true)} />
                <main className="dashboard-main">
                    {loading && activePage === "overview" ? <LoadingSpinner label="Preparing your energy dashboard…" /> : <>
                        <ErrorAlert message={error} title="Dashboard partially unavailable" onDismiss={() => setError("")} />
                        {activePage === "overview" && <OverviewPage predictions={predictions} health={health} onNavigate={setActivePage} />}
                        {activePage === "prediction" && <PredictionPage onPrediction={loadData} />}
                        {activePage === "reports" && <ReportsPage predictions={predictions} />}
                        {activePage === "anomalies" && <AnomaliesPage />}
                        {activePage === "peaks" && <PeakPredictionPage />}
                        {activePage === "profile" && <ProfilePage user={user} />}
                    </>}
                </main>
            </div>
        </div>
    );
}
