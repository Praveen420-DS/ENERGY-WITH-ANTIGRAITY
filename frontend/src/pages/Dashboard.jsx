import { useEffect, useState } from "react";

import Navbar from "../components/Navbar";
import PredictionPage from "./PredictionPage";
import Sidebar from "../components/Sidebar";
import StatCard from "../components/StatCard";
import UserProfile from "../components/UserProfile";
import { getUsers } from "../services/api";

function Dashboard({ onLogout }) {
    const [activePage, setActivePage] = useState("overview");
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        const fetchUser = async () => {
            try {
                setLoading(true);
                const users = await getUsers();
                if (users && users.length > 0) setUser(users[0]);
            } catch {
                setError("Unable to load authenticated user data.");
            } finally {
                setLoading(false);
            }
        };
        fetchUser();
    }, []);

    return (
        <div className="dashboard">
            <Navbar onLogout={onLogout} />
            <div className="dashboard-layout">
                <Sidebar activePage={activePage} setActivePage={setActivePage} />
                <main className="dashboard-main">
                    <div className="dashboard-header">
                        <h1>Energy Prediction Dashboard</h1>
                        <p>Monitor, analyze, and predict energy consumption using AI.</p>
                    </div>

                    {activePage === "overview" && (
                        <>
                            <div className="stats-grid">
                                <StatCard
                                    title="Total Energy"
                                    value="--"
                                    subtitle="Awaiting prediction data"
                                    icon="Energy"
                                />
                                <StatCard
                                    title="Today's Consumption"
                                    value="--"
                                    subtitle="No data available"
                                    icon="Trend"
                                />
                                <StatCard
                                    title="Prediction Status"
                                    value="Ready"
                                    subtitle="Production model integrated"
                                    icon="Model"
                                />
                                <StatCard
                                    title="System Status"
                                    value="Online"
                                    subtitle="Application is available"
                                    icon="Status"
                                />
                            </div>
                            <div className="dashboard-section">
                                <h2>Authenticated User</h2>
                                {loading && <p>Loading user information...</p>}
                                {error && <p className="error-message">{error}</p>}
                                {!loading && !error && user && <UserProfile user={user} />}
                            </div>
                        </>
                    )}

                    {activePage === "prediction" && <PredictionPage />}

                    {activePage === "reports" && (
                        <div className="dashboard-section">
                            <h2>Energy Reports</h2>
                            <p>Generated energy reports will appear here.</p>
                        </div>
                    )}

                    {activePage === "profile" && (
                        <div className="dashboard-section">
                            <h2>My Profile</h2>
                            {!loading && user && <UserProfile user={user} />}
                        </div>
                    )}
                </main>
            </div>
        </div>
    );
}

export default Dashboard;
