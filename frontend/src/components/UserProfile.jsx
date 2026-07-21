function UserProfile({ user }) {
    if (!user) {
        return (
            <div className="user-profile">
                <h3>User Profile</h3>
                <p>No user data available.</p>
            </div>
        );
    }

    return (
        <div className="user-profile">
            <div className="user-profile-header">
                <div className="user-avatar">
                    {user.username
                        ? user.username.charAt(0).toUpperCase()
                        : "U"}
                </div>

                <div>
                    <h3>
                        {user.full_name || user.username}
                    </h3>

                    <p>
                        {user.email}
                    </p>
                </div>
            </div>

            <div className="user-profile-details">
                <div className="profile-row">
                    <strong>ID:</strong>
                    <span>{user.id}</span>
                </div>

                <div className="profile-row">
                    <strong>Username:</strong>
                    <span>{user.username}</span>
                </div>

                <div className="profile-row">
                    <strong>Email:</strong>
                    <span>{user.email}</span>
                </div>

                <div className="profile-row">
                    <strong>Full Name:</strong>
                    <span>{user.full_name || "Not provided"}</span>
                </div>

                <div className="profile-row">
                    <strong>Role:</strong>
                    <span>{user.role}</span>
                </div>

                <div className="profile-row">
                    <strong>Status:</strong>

                    <span>
                        {user.is_active
                            ? "🟢 Active"
                            : "🔴 Inactive"}
                    </span>
                </div>
            </div>
        </div>
    );
}

export default UserProfile;