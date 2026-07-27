import { useState } from "react";

import Login from "./pages/Login";
import Register from "./pages/Register";
import ForgotPassword from "./pages/ForgotPassword";
import Dashboard from "./pages/Dashboard";

function App() {

  const [
    isAuthenticated,
    setIsAuthenticated
  ] = useState(
    !!localStorage.getItem(
      "access_token"
    )
  );
  const [authScreen, setAuthScreen] = useState("login");

  const handleLogin = () => {

    setIsAuthenticated(true);

  };

  const handleLogout = () => {

    localStorage.removeItem(
      "access_token"
    );

    setIsAuthenticated(false);

  };

  if (!isAuthenticated) {
    if (authScreen === "forgot-password") {
      return <ForgotPassword onBack={() => setAuthScreen("login")} />;
    }
    return authScreen === "register"
      ? <Register onLogin={() => setAuthScreen("login")} />
      : <Login onLogin={handleLogin} onRegister={() => setAuthScreen("register")} onForgot={() => setAuthScreen("forgot-password")} />;

  }

  return (
    <Dashboard
      onLogout={handleLogout}
    />
  );
}

export default App;
