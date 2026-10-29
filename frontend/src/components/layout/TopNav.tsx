import { useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { Aperture } from "lucide-react";
import { usePolling } from "../../hooks/usePolling";
import { api } from "../../api/client";

const NAV = [
  { path: "/", label: "Check Image", end: true },
  { path: "/pipeline", label: "Pipeline" },
  { path: "/review", label: "Review" },
  { path: "/how-it-works", label: "How It Works" },
];

export default function TopNav() {
  const navigate = useNavigate();
  const [scrolled, setScrolled] = useState(false);
  const worker = usePolling(() => api.worker(), 1000);
  const health = usePolling(() => api.health(), 5000);
  const backendLabel = health?.cv_backend === "local" ? "Real CV (on-device)"
    : health?.cv_backend === "patchcore" ? "PatchCore" : "Simulated CV";

  useEffect(() => {
    const h = () => setScrolled(window.scrollY > 24);
    window.addEventListener("scroll", h, { passive: true });
    return () => window.removeEventListener("scroll", h);
  }, []);

  const wstate = worker?.state ?? "stopped";

  return (
    <nav className={`top-navbar${scrolled ? " scrolled" : ""}`}>
      <div className="navbar-brand" onClick={() => navigate("/")} role="button" tabIndex={0}>
        <span className="brand-mark">
          <Aperture size={18} color="#fff" strokeWidth={2.4} />
        </span>
        <span className="brand-name">
          Vision<span>Flow</span>
        </span>
      </div>
      <div className="navbar-links">
        {NAV.map(({ path, label, end }) => (
          <NavLink key={path} to={path} end={end}
            className={({ isActive }) => `navbar-link${isActive ? " active" : ""}`}>
            {label}
          </NavLink>
        ))}
      </div>
      <div className="navbar-right">
        <span className="chip-sim" title="Computer-vision backend in use; no external APIs">
          {backendLabel}
        </span>
        <span className="worker-pill" title="Durable worker state">
          <span className={`dot ${wstate}`} />
          worker: {wstate}
        </span>
      </div>
    </nav>
  );
}
