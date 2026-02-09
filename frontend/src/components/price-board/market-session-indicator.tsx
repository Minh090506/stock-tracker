/** Colored badge showing current VN market session. Auto-refreshes every 15s. */

import { useState, useEffect } from "react";
import { getMarketSession } from "../../utils/market-session";

const REFRESH_INTERVAL_MS = 15_000;

export function MarketSessionIndicator() {
  const [info, setInfo] = useState(() => getMarketSession());

  useEffect(() => {
    const id = setInterval(() => setInfo(getMarketSession()), REFRESH_INTERVAL_MS);
    return () => clearInterval(id);
  }, []);

  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-gray-800 px-2.5 py-0.5 text-xs font-medium text-gray-300">
      <span className={`inline-block h-2 w-2 rounded-full ${info.colorClass}`} />
      {info.label}
    </span>
  );
}
