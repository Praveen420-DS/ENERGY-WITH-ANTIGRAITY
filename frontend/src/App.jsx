import { useState } from "react";

import Login from "./pages/Login";
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

    return (
      <Login
        onLogin={handleLogin}
      />
    );

  }

  return (
    <Dashboard
      onLogout={handleLogout}
    />
  );
}

export default App;