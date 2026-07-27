import { BarChart3, Bolt, FileBarChart, Gauge, UserRound, X } from "lucide-react";

const items = [
    { id: "overview", label: "Overview", icon: Gauge },
    { id: "prediction", label: "New prediction", icon: Bolt },
    { id: "reports", label: "Reports", icon: FileBarChart },
    { id: "profile", label: "Profile", icon: UserRound },
];

export default function Sidebar({ activePage, setActivePage, open, onClose }) {
    const select = (id) => { setActivePage(id); onClose(); };
    return (
        <>
            <aside className={`sidebar ${open ? "open" : ""}`}>
                <div className="sidebar-brand"><span><BarChart3 /></span><div><strong>Enerlytics</strong><small>AI energy intelligence</small></div><button className="sidebar-close" onClick={onClose} aria-label="Close navigation"><X /></button></div>
                <nav className="sidebar-menu" aria-label="Primary navigation">
                    <p className="nav-label">Workspace</p>
                    {items.map(({ id, label, icon: Icon }) => <button key={id} className={`sidebar-item ${activePage === id ? "active" : ""}`} onClick={() => select(id)}><Icon size={19} /><span>{label}</span></button>)}
                </nav>
                <div className="sidebar-foot"><span className="status-dot" /><div><strong>System operational</strong><small>Production environment</small></div></div>
            </aside>
            {open && <button className="sidebar-scrim" onClick={onClose} aria-label="Close navigation" />}
        </>
    );
}
