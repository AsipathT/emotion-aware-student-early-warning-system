import { ClipboardList, History, LayoutDashboard, Users } from "lucide-react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { ReferenceProvider } from "../reference";
import { Avatar } from "./ui";

const NAV = [
  { to: "/students", label: "Students", Icon: Users, match: (p) => p === "/students" || p.endsWith("/assess") },
  { to: "/dashboard", label: "Dashboard", Icon: LayoutDashboard, match: (p) => p === "/dashboard" || /^\/students\/[^/]+$/.test(p) },
  {
    to: "/recommendations",
    label: "Intervention Recommendations",
    Icon: ClipboardList,
    match: (p) => p === "/recommendations" || p.startsWith("/assessments/"),
  },
  { to: "/history", label: "Intervention History", Icon: History, match: (p) => p.startsWith("/history") },
];

export default function Layout() {
  const { pathname } = useLocation();

  return (
    <ReferenceProvider>
      <div className="app">
        <aside className="sidebar">
          <div className="brand">
            <div className="brand-logo">C4</div>
            <div className="brand-text">Adaptive Intervention Recommendation</div>
          </div>
          <nav className="nav">
            {NAV.map(({ to, label, Icon, match }) => (
              <Link key={to} to={to} className={`nav-item ${match(pathname) ? "active" : ""}`}>
                <Icon size={19} aria-hidden="true" />
                <span>{label}</span>
              </Link>
            ))}
          </nav>
          <div className="sidebar-user">
            <Avatar name="Counsellor" size={38} initialsOverride="C" />
            <div className="sidebar-user-text">
              <strong>Counsellor</strong>
            </div>
          </div>
        </aside>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </ReferenceProvider>
  );
}
