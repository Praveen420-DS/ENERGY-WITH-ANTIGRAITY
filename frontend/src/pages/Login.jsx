import { useState } from "react";
import { loginUser } from "../services/api";

function Login({ onLogin }) {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");

    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

    const handleLogin = async (e) => {
        e.preventDefault();

        setError("");
        setLoading(true);

        try {
            // Call backend login API
            const data = await loginUser(email, password);

            // Check if access token exists
            if (data.access_token) {

                // Save JWT token
                localStorage.setItem(
                    "access_token",
                    data.access_token
                );

                // Tell App.jsx login was successful
                if (onLogin) {
                    onLogin();
                }

            } else {
                setError("Login failed: No access token received");
            }

        } catch (error) {

            if (error.response) {
                setError(
                    error.response.data?.detail ||
                    "Incorrect email or password"
                );
            } else {
                setError(
                    "Unable to connect to the backend server"
                );
            }

        } finally {
            setLoading(false);
        }
    };


    return (
        <div className="login-container">

            <h1>Energy Prediction System</h1>

            <h2>Login</h2>

            <form onSubmit={handleLogin}>

                <div>
                    <label htmlFor="email">
                        Email
                    </label>

                    <input
                        id="email"
                        name="email"
                        type="email"
                        value={email}
                        onChange={(e) =>
                            setEmail(e.target.value)
                        }
                        placeholder="Enter your email"
                        required
                    />
                </div>


                <div>
                    <label htmlFor="password">
                        Password
                    </label>

                    <input
                        id="password"
                        name="password"
                        type="password"
                        value={password}
                        onChange={(e) =>
                            setPassword(e.target.value)
                        }
                        placeholder="Enter your password"
                        required
                    />
                </div>


                <button
                    type="submit"
                    disabled={loading}
                >
                    {loading ? "Logging in..." : "Login"}
                </button>

            </form>


            {error && (
                <p className="login-error" role="alert">
                    {error}
                </p>
            )}

        </div>
    );
}

export default Login;
