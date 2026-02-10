/** Real-time alerts hook — WS stream with REST polling fallback and sound notifications. */

import { useState, useEffect, useRef, useCallback } from "react";
import { useWebSocket } from "./use-websocket";
import type { Alert, AlertType, AlertSeverity } from "../types";

const API_BASE = "/api/market";
const MAX_ALERTS = 200;

// -- Fallback fetcher --

async function fetchAlerts(): Promise<Alert[]> {
  const res = await fetch(`${API_BASE}/alerts?limit=50`);
  if (!res.ok) throw new Error(`GET /api/alerts failed: ${res.status}`);
  return res.json();
}

// -- Sound notification --

let audioCtx: AudioContext | null = null;

function playCriticalBeep() {
  try {
    if (!audioCtx) audioCtx = new AudioContext();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.frequency.value = 880;
    gain.gain.value = 0.15;
    osc.start();
    osc.stop(audioCtx.currentTime + 0.15);
  } catch {
    // AudioContext may be blocked before user interaction — silently ignore
  }
}

// -- Hook --

export interface UseAlertsOptions {
  soundEnabled?: boolean;
}

export interface UseAlertsResult {
  alerts: Alert[];
  isLive: boolean;
  error: Error | null;
  soundEnabled: boolean;
  toggleSound: () => void;
}

export function useAlerts(options: UseAlertsOptions = {}): UseAlertsResult {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [soundEnabled, setSoundEnabled] = useState(options.soundEnabled ?? false);
  const seenIdsRef = useRef(new Set<string>());

  const { data, isLive, error } = useWebSocket<Alert | Alert[]>("alerts", {
    fallbackFetcher: fetchAlerts,
    fallbackIntervalMs: 10_000,
  });

  // Accumulate alerts from WS (single alert) or REST (array)
  useEffect(() => {
    if (!data) return;

    const incoming = Array.isArray(data) ? data : [data];
    const fresh = incoming.filter((a) => !seenIdsRef.current.has(a.id));
    if (fresh.length === 0) return;

    for (const a of fresh) seenIdsRef.current.add(a.id);

    // Sound for critical alerts
    if (soundEnabled) {
      const hasCritical = fresh.some((a) => a.severity === "critical");
      if (hasCritical) playCriticalBeep();
    }

    setAlerts((prev) => {
      const merged = [...fresh, ...prev];
      const trimmed = merged.slice(0, MAX_ALERTS);
      // Prune seen IDs to match retained alerts — prevents unbounded Set growth
      const retained = new Set(trimmed.map((a) => a.id));
      seenIdsRef.current = retained;
      return trimmed;
    });
  }, [data, soundEnabled]);

  const toggleSound = useCallback(() => setSoundEnabled((s) => !s), []);

  return { alerts, isLive, error, soundEnabled, toggleSound };
}

// -- Filter utility --

export function filterAlerts(
  alerts: Alert[],
  typeFilter: AlertType | "all",
  severityFilter: AlertSeverity | "all",
): Alert[] {
  return alerts.filter(
    (a) =>
      (typeFilter === "all" || a.alert_type === typeFilter) &&
      (severityFilter === "all" || a.severity === severityFilter),
  );
}
