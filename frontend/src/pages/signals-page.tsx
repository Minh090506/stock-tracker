/** Signals page — displays real-time analytics alerts with type/severity filtering. */

import { useState } from "react";
import type { AlertType, AlertSeverity } from "../types";
import { useAlerts, filterAlerts } from "../hooks/use-alerts";
import { SignalFilterChips } from "../components/signals/signal-filter-chips";
import { SignalFeedList } from "../components/signals/signal-feed-list";
import { ErrorBanner } from "../components/ui/error-banner";

export default function SignalsPage() {
  const [typeFilter, setTypeFilter] = useState<AlertType | "all">("all");
  const [severityFilter, setSeverityFilter] = useState<AlertSeverity | "all">("all");

  const { alerts, isLive, error, soundEnabled, toggleSound } = useAlerts();
  const filtered = filterAlerts(alerts, typeFilter, severityFilter);

  return (
    <div className="p-6 space-y-6">
      {/* Header with connection status and sound toggle */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-white">Signals</h1>
          <span
            className={`inline-block w-2 h-2 rounded-full ${isLive ? "bg-green-500" : "bg-yellow-500"}`}
            title={isLive ? "Live (WebSocket)" : "Polling (REST fallback)"}
          />
        </div>
        <button
          onClick={toggleSound}
          className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
            soundEnabled
              ? "bg-red-900/60 text-red-300"
              : "bg-gray-800 text-gray-400 hover:bg-gray-700"
          }`}
          title={soundEnabled ? "Sound ON for critical alerts" : "Sound OFF"}
        >
          {soundEnabled ? "Sound ON" : "Sound OFF"}
        </button>
      </div>

      {error && <ErrorBanner message={error.message} />}

      <SignalFilterChips
        activeType={typeFilter}
        activeSeverity={severityFilter}
        onTypeChange={setTypeFilter}
        onSeverityChange={setSeverityFilter}
      />

      <SignalFeedList alerts={filtered} />
    </div>
  );
}
