/** Sidebar navigation with links to analysis pages. */

import { NavLink } from "react-router-dom";

const NAV_ITEMS = [
  { to: "/foreign-flow", label: "Foreign Flow" },
  { to: "/volume", label: "Volume Analysis" },
  { to: "/signals", label: "Signals" },
] as const;

export function AppSidebarNavigation() {
  return (
    <aside className="w-60 shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col">
      <div className="p-4 border-b border-gray-800">
        <h1 className="text-lg font-bold text-white tracking-tight">
          VN Stock Tracker
        </h1>
        <p className="text-xs text-gray-500 mt-1">Real-time VN30 Analytics</p>
      </div>

      <nav className="flex-1 p-3 space-y-1">
        {NAV_ITEMS.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `block px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                isActive
                  ? "bg-gray-800 text-white"
                  : "text-gray-400 hover:text-white hover:bg-gray-800/50"
              }`
            }
          >
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-gray-800 text-xs text-gray-600">
        SSI FastConnect
      </div>
    </aside>
  );
}
