/** Signal feed list — reverse chronological display of market signals. */

import type { Signal, SignalSeverity } from "../../types";

interface SignalFeedListProps {
  signals: Signal[];
}

const SEVERITY_STYLES: Record<
  SignalSeverity,
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

function extractTime(isoTimestamp: string): string {
  const date = new Date(isoTimestamp);
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  const seconds = String(date.getSeconds()).padStart(2, "0");
  return `${hours}:${minutes}:${seconds}`;
}

function SignalCard({ signal }: { signal: Signal }) {
  const styles = SEVERITY_STYLES[signal.severity];
  const time = extractTime(signal.timestamp);

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-3 flex items-center gap-3">
      <span className="text-gray-400 text-sm font-mono shrink-0">{time}</span>
      <span
        className={`
          ${styles.bg} ${styles.text} ${styles.border}
          border px-2 py-1 rounded text-xs font-medium uppercase shrink-0
        `}
      >
        {signal.severity}
      </span>
      <span className="text-white font-medium shrink-0">{signal.symbol}</span>
      <span className="text-gray-300 text-sm">{signal.message}</span>
    </div>
  );
}

export function SignalFeedList({ signals }: SignalFeedListProps) {
  if (signals.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-gray-500">No signals yet. Monitoring market...</p>
      </div>
    );
  }

  return (
    <div className="space-y-2 max-h-[calc(100vh-200px)] overflow-y-auto">
      {signals.map((signal) => (
        <SignalCard key={signal.id} signal={signal} />
      ))}
    </div>
  );
}
