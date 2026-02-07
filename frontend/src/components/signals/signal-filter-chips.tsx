/** Filter chips for signal types — clickable buttons to filter signal feed. */

import type { SignalType } from "../../types";

interface SignalFilterChipsProps {
  active: SignalType | "all";
  onChange: (filter: SignalType | "all") => void;
}

type FilterOption = SignalType | "all";

const FILTER_OPTIONS: { value: FilterOption; label: string }[] = [
  { value: "all", label: "All" },
  { value: "foreign", label: "Foreign" },
  { value: "volume", label: "Volume" },
  { value: "divergence", label: "Divergence" },
];

export function SignalFilterChips({ active, onChange }: SignalFilterChipsProps) {
  return (
    <div className="flex gap-2">
      {FILTER_OPTIONS.map((option) => {
        const isActive = active === option.value;
        return (
          <button
            key={option.value}
            onClick={() => onChange(option.value)}
            className={`
              px-4 py-2 rounded-lg text-sm transition-colors
              ${
                isActive
                  ? "bg-white text-gray-900 font-medium"
                  : "bg-gray-800 text-gray-400 hover:bg-gray-700"
              }
            `}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
