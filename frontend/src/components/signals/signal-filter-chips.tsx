/** Filter chips for alert type and severity — clickable buttons to filter alert feed. */

import type { AlertType, AlertSeverity } from "../../types";

type TypeFilter = AlertType | "all";
type SeverityFilter = AlertSeverity | "all";

interface SignalFilterChipsProps {
  activeType: TypeFilter;
  activeSeverity: SeverityFilter;
  onTypeChange: (filter: TypeFilter) => void;
  onSeverityChange: (filter: SeverityFilter) => void;
}

const TYPE_OPTIONS: { value: TypeFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "foreign_acceleration", label: "Foreign" },
  { value: "volume_spike", label: "Volume" },
  { value: "basis_divergence", label: "Basis" },
  { value: "price_breakout", label: "Breakout" },
];

const SEVERITY_OPTIONS: { value: SeverityFilter; label: string; color: string }[] = [
  { value: "all", label: "All", color: "" },
  { value: "critical", label: "Critical", color: "bg-red-900/60 text-red-300" },
  { value: "warning", label: "Warning", color: "bg-yellow-900/60 text-yellow-300" },
  { value: "info", label: "Info", color: "bg-blue-900/60 text-blue-300" },
];

function ChipButton({
  active,
  onClick,
  colorClass,
  children,
}: {
  active: boolean;
  onClick: () => void;
  colorClass?: string;
  children: React.ReactNode;
}) {
  const base = "px-3 py-1.5 rounded-lg text-sm transition-colors";
  const cls = active
    ? colorClass || "bg-white text-gray-900 font-medium"
    : "bg-gray-800 text-gray-400 hover:bg-gray-700";
  return (
    <button onClick={onClick} className={`${base} ${cls}`}>
      {children}
    </button>
  );
}

export function SignalFilterChips({
  activeType,
  activeSeverity,
  onTypeChange,
  onSeverityChange,
}: SignalFilterChipsProps) {
  return (
    <div className="flex flex-wrap items-center gap-4">
      {/* Type filter */}
      <div className="flex gap-1.5">
        {TYPE_OPTIONS.map((o) => (
          <ChipButton key={o.value} active={activeType === o.value} onClick={() => onTypeChange(o.value)}>
            {o.label}
          </ChipButton>
        ))}
      </div>

      <span className="text-gray-600">|</span>

      {/* Severity filter */}
      <div className="flex gap-1.5">
        {SEVERITY_OPTIONS.map((o) => (
          <ChipButton
            key={o.value}
            active={activeSeverity === o.value}
            onClick={() => onSeverityChange(o.value)}
            colorClass={o.color || undefined}
          >
            {o.label}
          </ChipButton>
        ))}
      </div>
    </div>
  );
}
