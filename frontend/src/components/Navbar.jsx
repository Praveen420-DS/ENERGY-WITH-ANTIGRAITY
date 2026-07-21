function Navbar({ onLogout }) {
    return (
        <nav className="navbar">
            <div className="navbar-brand">
                <h2>⚡ Energy Prediction System</h2>
            </div>

            <div className="navbar-actions">
                <span className="navbar-status">
                    🟢 System Online
                </span>

                <button
                    className="logout-button"
                    onClick={onLogout}
                >
                    Logout
                </button>
            </div>
        </nav>
    );
}

export default Navbar;