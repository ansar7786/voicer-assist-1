import { Link, useLocation } from "react-router-dom";

export default function Navbar() {
  const location = useLocation();

  const navLinkStyle = (path) => {
    const isActive = location.pathname === path || (path === "/consent" && location.pathname === "/");
    return {
      padding: "0.5rem 1rem",
      textDecoration: "none",
      fontWeight: isActive ? "bold" : "normal",
      color: isActive ? "#1e40af" : "#475569",
      borderBottom: isActive ? "2px solid #1e40af" : "2px solid transparent",
    };
  };

  return (
    <header
      style={{
        borderBottom: "1px solid #e2e8f0",
        backgroundColor: "#ffffff",
        padding: "0.75rem 2rem",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
        <span style={{ fontSize: "1.25rem", fontWeight: "bold", color: "#0f172a" }}>
          SIH26097 Live Voice Assistant
        </span>
        <span
          style={{
            fontSize: "0.75rem",
            backgroundColor: "#dbeafe",
            color: "#1e40af",
            padding: "0.2rem 0.5rem",
            borderRadius: "4px",
            fontWeight: "bold",
          }}
        >
          Phase 1
        </span>
      </div>

      <nav style={{ display: "flex", gap: "1rem" }}>
        <Link to="/consent" style={navLinkStyle("/consent")}>
          Consent
        </Link>
        <Link to="/live" style={navLinkStyle("/live")}>
          Live Voice Console
        </Link>
        <Link to="/official" style={navLinkStyle("/official")}>
          Official View
        </Link>
      </nav>
    </header>
  );
}
