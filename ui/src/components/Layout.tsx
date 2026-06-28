import { Link, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function Layout() {
  const { user, logout } = useAuth();

  return (
    <div className="app-shell">
      <header className="app-header">
        <Link to="/workspaces" className="brand">
          EDM Platform
        </Link>
        <nav>
          <Link to="/workspaces">Workspaces</Link>
        </nav>
        <div className="header-user">
          {user && (
            <>
              <span>{user.email}</span>
              <button onClick={logout}>Log out</button>
            </>
          )}
        </div>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
