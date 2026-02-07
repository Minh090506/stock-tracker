/** Signals page — displays market signals with type filtering. */

import { useState } from "react";
import type { SignalType, Signal } from "../types";
import { useSignals } from "../hooks/use-signals-mock";
import { SignalFilterChips } from "../components/signals/signal-filter-chips";
import { SignalFeedList } from "../components/signals/signal-feed-list";

export default function SignalsPage() {
  const [activeFilter, setActiveFilter] = useState<SignalType | "all">("all");
  const { signals } = useSignals();

  const filteredSignals: Signal[] =
    activeFilter === "all"
      ? signals
      : signals.filter((signal) => signal.type === activeFilter);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-white">Signals</h1>

      <SignalFilterChips active={activeFilter} onChange={setActiveFilter} />

      <SignalFeedList signals={filteredSignals} />
    </div>
  );
}
