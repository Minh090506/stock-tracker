/** Time-based VN stock market session detection (HOSE schedule). */

export type MarketSession =
  | "pre-market"
  | "ato"
  | "continuous"
  | "lunch"
  | "atc"
  | "plo"
  | "closed";

interface SessionInfo {
  session: MarketSession;
  label: string;
  /** Dot color class for indicator */
  colorClass: string;
}

/** HOSE trading schedule in minutes since midnight (VN time). */
const ATO_START = 9 * 60;       // 09:00
const ATO_END = 9 * 60 + 15;    // 09:15
const MORNING_END = 11 * 60 + 30; // 11:30
const AFTERNOON_START = 13 * 60; // 13:00
const AFTERNOON_END = 14 * 60 + 30; // 14:30
const ATC_END = 14 * 60 + 45;   // 14:45
const PLO_END = 15 * 60;        // 15:00

/**
 * Get current VN market session based on wall clock time.
 * Uses Asia/Ho_Chi_Minh timezone regardless of browser locale.
 * Note: does not account for VN public holidays (Tet, etc.) — shows pre-market/continuous instead of closed.
 */
export function getMarketSession(now?: Date): SessionInfo {
  const date = now ?? new Date();

  // Format in VN timezone to get local hours/minutes/day
  const vnParts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Ho_Chi_Minh",
    hour: "numeric",
    minute: "numeric",
    weekday: "short",
    hour12: false,
  }).formatToParts(date);

  const hour = Number(vnParts.find((p) => p.type === "hour")?.value ?? 0);
  const minute = Number(vnParts.find((p) => p.type === "minute")?.value ?? 0);
  const weekday = vnParts.find((p) => p.type === "weekday")?.value ?? "";

  // Weekends: always closed
  if (weekday === "Sat" || weekday === "Sun") {
    return { session: "closed", label: "Closed", colorClass: "bg-gray-500" };
  }

  const mins = hour * 60 + minute;

  if (mins < ATO_START) {
    return { session: "pre-market", label: "Pre-market", colorClass: "bg-blue-500" };
  }
  if (mins < ATO_END) {
    return { session: "ato", label: "ATO", colorClass: "bg-yellow-500" };
  }
  if (mins < MORNING_END) {
    return { session: "continuous", label: "Continuous", colorClass: "bg-green-500" };
  }
  if (mins < AFTERNOON_START) {
    return { session: "lunch", label: "Lunch Break", colorClass: "bg-orange-400" };
  }
  if (mins < AFTERNOON_END) {
    return { session: "continuous", label: "Continuous", colorClass: "bg-green-500" };
  }
  if (mins < ATC_END) {
    return { session: "atc", label: "ATC", colorClass: "bg-yellow-500" };
  }
  if (mins < PLO_END) {
    return { session: "plo", label: "PLO", colorClass: "bg-purple-400" };
  }

  return { session: "closed", label: "Closed", colorClass: "bg-gray-500" };
}
