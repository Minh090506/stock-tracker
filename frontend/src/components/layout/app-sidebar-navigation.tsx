/** Sidebar navigation — static on desktop, overlay drawer on mobile. */

import { NavLink, useLocation } from "react-router-dom";
import { useEffect } from "react";

interface AppSidebarNavigationProps {
  isOpen: boolean;
  onClose: () => void;
}

const NAV_ITEMS = [
  { to: "/price-board", label: "Price Board" },
  { to: "/foreign-flow", label: "Foreign Flow" },
  { to: "/volume", label: "Volume Analysis" },
  { to: "/derivatives", label: "Derivatives" },
  { to: "/signals", label: "Signals" },
] as const;

export function AppSidebarNavigation({ isOpen, onClose }: AppSidebarNavigationProps) {
  const location = useLocation();

  // Close sidebar on route change (mobile)
  useEffect(() => {
    onClose();
  }, [location.pathname, onClose]);

  return (
    <>
      {/* Backdrop (mobile only) */}
      {isOpen && (
        <div
          className="md:hidden fixed inset-0 bg-black/50 z-40"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          w-60 shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col z-50
          fixed md:static inset-y-0 left-0
          transition-transform duration-200
          ${isOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}
        `}
      >
        <div className="p-4 border-b border-gray-800 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-white tracking-tight">
              VN Stock Tracker
            </h1>
            <p className="text-xs text-gray-500 mt-1">Real-time VN30 Analytics</p>
          </div>
          <button
            onClick={onClose}
            className="md:hidden p-1 text-gray-400 hover:text-white"
            aria-label="Close menu"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          {NAV_ITEMS.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `block px-3 py-2.5 rounded-md text-sm font-medium transition-colors ${
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
    </>
  );
}
