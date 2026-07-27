import { Bell, ChevronDown, LogOut, Menu, Search } from "lucide-react";

export default function Navbar({ onLogout, user, onMenu }) {
    const name = user?.full_name || user?.username || "Account";
    return (
        <header className="navbar">
            <button className="menu-button" onClick={onMenu} aria-label="Open navigation"><Menu /></button>
            <div className="nav-search"><Search size={18} /><input aria-label="Search" placeholder="Search predictions and reports" /></div>
            <div className="navbar-actions">
                <button className="icon-button" aria-label="Notifications"><Bell size={19} /></button>
                <div className="nav-user"><span className="avatar avatar-small">{name.charAt(0).toUpperCase()}</span><div><strong>{name}</strong><small>{user?.role || "User"}</small></div><ChevronDown size={15} /></div>
                <button className="icon-button logout" onClick={onLogout} aria-label="Log out" title="Log out"><LogOut size={19} /></button>
            </div>
        </header>
    );
}
