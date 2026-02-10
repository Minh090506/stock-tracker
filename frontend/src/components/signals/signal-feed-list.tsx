/** Alert feed list — reverse chronological display of market alerts with auto-scroll. */

import { useEffect, useRef } from "react";
import type { Alert, AlertType, AlertSeverity } from "../../types";

interface SignalFeedListProps {
  alerts: Alert[];
}

const SEVERITY_STYLES: Record<
  AlertSeverity,
  { bg: string; text: string; border: string }
> = {
  info: {
    bg: "bg-blue-900/50",
    text: "text-blue-300",
    border: "border-blue-700",
  },
  warning: {
    bg: "bg-yellow-900/50",
    text: "text-yellow-300",
    border: "border-yellow-700",
  },
  critical: {
    bg: "bg-red-900/50",
    text: "text-red-300",
    border: "border-red-700",
  },
};

const TYPE_ICONS: Record<AlertType, string> = {
  foreign_acceleration: "NN",
  basis_divergence: "BD",
  volume_spike: "VS",
  price_breakout: "PB",
};

const TYPE_COLORS: Record<AlertType, string> = {
  foreign_acceleration: "text-fuchsia-400",
  basis_divergence: "text-cyan-400",
  volume_spike: "text-orange-400",
  price_breakout: "text-emerald-400",
};

function extractTime(isoTimestamp: string): string {
  const date = new Date(isoTimestamp);
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  const seconds = String(date.getSeconds()).padStart(2, "0");
  return `${hours}:${minutes}:${seconds}`;
}

function AlertCard({ alert }: { alert: Alert }) {
  const styles = SEVERITY_STYLES[alert.severity];
  const time = extractTime(alert.timestamp);
  const icon = TYPE_ICONS[alert.alert_type];
  const iconColor = TYPE_COLORS[alert.alert_type];

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-3 flex items-center gap-3">
      <span className="text-gray-400 text-sm font-mono shrink-0">{time}</span>
      <span
        className={`${styles.bg} ${styles.text} ${styles.border} border px-2 py-1 rounded text-xs font-medium uppercase shrink-0`}
      >
        {alert.severity}
      </span>
      <span className={`${iconColor} text-xs font-bold shrink-0 w-6 text-center`}>{icon}</span>
      <span className="text-white font-medium shrink-0">{alert.symbol}</span>
      <span className="text-gray-300 text-sm">{alert.message}</span>
    </div>
  );
}

export function SignalFeedList({ alerts }: SignalFeedListProps) {
  const listRef = useRef<HTMLDivElement>(null);
  const prevCountRef = useRef(alerts.length);

  // Auto-scroll to top when new alerts arrive
  useEffect(() => {
    if (alerts.length > prevCountRef.current && listRef.current) {
      listRef.current.scrollTop = 0;
    }
    prevCountRef.current = alerts.length;
  }, [alerts.length]);

  if (alerts.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-gray-500">No alerts yet. Monitoring market...</p>
      </div>
    );
  }

  return (
    <div ref={listRef} className="space-y-2 max-h-[calc(100vh-200px)] overflow-y-auto">
      {alerts.map((alert) => (
        <AlertCard key={alert.id} alert={alert} />
      ))}
    </div>
  );
}
