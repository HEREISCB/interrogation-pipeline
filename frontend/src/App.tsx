import { NavLink, Route, Routes, Navigate } from "react-router-dom";

import Today from "@/pages/Today";
import Calendar from "@/pages/Calendar";
import Channels from "@/pages/Channels";
import Runs from "@/pages/Runs";
import Settings from "@/pages/Settings";
import Stats from "@/pages/Stats";
import HealthBanner from "@/components/HealthBanner";

const tabs = [
  { to: "/today", label: "Today" },
  { to: "/calendar", label: "Calendar" },
  { to: "/channels", label: "Channels" },
  { to: "/runs", label: "Runs" },
  { to: "/stats", label: "Stats" },
  { to: "/settings", label: "Settings" },
];

export default function App() {
  return (
    <div className="min-h-screen bg-white text-ink">
      <header className="border-b border-line bg-white sticky top-0 z-20">
        <div className="max-w-6xl mx-auto px-5 py-3 flex items-center gap-6">
          <div className="font-semibold text-base tracking-tight">
            Interrogation Pipeline
            <span className="ml-2 text-xs font-normal text-soft">v0.1</span>
          </div>
          <nav className="flex items-center gap-1 text-sm">
            {tabs.map((t) => (
              <NavLink
                key={t.to}
                to={t.to}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded-md transition-colors ${
                    isActive
                      ? "bg-accent text-white"
                      : "text-soft hover:bg-bg-soft hover:text-ink"
                  }`
                }
              >
                {t.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <HealthBanner />
      <main className="max-w-6xl mx-auto px-5 py-6">
        <Routes>
          <Route path="/" element={<Navigate to="/today" replace />} />
          <Route path="/today" element={<Today />} />
          <Route path="/calendar" element={<Calendar />} />
          <Route path="/channels" element={<Channels />} />
          <Route path="/runs" element={<Runs />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/stats" element={<Stats />} />
          <Route path="*" element={<Navigate to="/today" replace />} />
        </Routes>
      </main>
    </div>
  );
}
