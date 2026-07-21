function Sidebar({ activePage, setActivePage }) {
    const menuItems = [
        {
            id: "overview",
            label: "Overview",
            icon: "📊",
        },
        {
            id: "prediction",
            label: "Prediction",
            icon: "🔮",
        },
        {
            id: "reports",
            label: "Reports",
            icon: "📄",
        },
        {
            id: "profile",
            label: "Profile",
            icon: "👤",
        },
    ];

    return (
        <aside className="sidebar">
            <div className="sidebar-header">
                <h3>Menu</h3>
            </div>

            <div className="sidebar-menu">
                {menuItems.map((item) => (
                    <button
                        key={item.id}
                        className={
                            activePage === item.id
                                ? "sidebar-item active"
                                : "sidebar-item"
                        }
                        onClick={() => setActivePage(item.id)}
                    >
                        <span className="sidebar-icon">
                            {item.icon}
                        </span>

                        <span>
                            {item.label}
                        </span>
                    </button>
                ))}
            </div>
        </aside>
    );
}

export default Sidebar;