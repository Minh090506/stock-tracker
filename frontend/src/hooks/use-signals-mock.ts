/** Mock signals hook — returns static sample data until analytics engine ships. */

import type { Signal } from "../types";

const now = new Date();

function minutesAgo(m: number): string {
  return new Date(now.getTime() - m * 60_000).toISOString();
}

const MOCK_SIGNALS: Signal[] = [
  {
    id: "1",
    type: "foreign",
    severity: "critical",
    symbol: "VNM",
    message: "Foreign buy acceleration 3.2x above normal",
    value: 3.2,
    timestamp: minutesAgo(2),
  },
  {
    id: "2",
    type: "volume",
    severity: "warning",
    symbol: "HPG",
    message: "Active buy ratio surged to 72%",
    value: 72,
    timestamp: minutesAgo(5),
  },
  {
    id: "3",
    type: "divergence",
    severity: "info",
    symbol: "VN30F",
    message: "Basis premium expanded to 1.3%",
    value: 1.3,
    timestamp: minutesAgo(8),
  },
  {
    id: "4",
    type: "foreign",
    severity: "warning",
    symbol: "MBB",
    message: "Foreign sell speed 2.1x normal rate",
    value: 2.1,
    timestamp: minutesAgo(12),
  },
  {
    id: "5",
    type: "volume",
    severity: "critical",
    symbol: "SSI",
    message: "Volume spike 4.5x 20-day average",
    value: 4.5,
    timestamp: minutesAgo(15),
  },
  {
    id: "6",
    type: "divergence",
    severity: "warning",
    symbol: "VN30F",
    message: "Basis flipped from premium to discount",
    value: -0.2,
    timestamp: minutesAgo(20),
  },
  {
    id: "7",
    type: "foreign",
    severity: "info",
    symbol: "FPT",
    message: "Foreign net buy crossed 1M shares",
    value: 1_000_000,
    timestamp: minutesAgo(25),
  },
  {
    id: "8",
    type: "volume",
    severity: "info",
    symbol: "VIC",
    message: "Active sell ratio rising — now at 61%",
    value: 61,
    timestamp: minutesAgo(30),
  },
];

export function useSignals() {
  return { signals: MOCK_SIGNALS };
}
