/** Generic WebSocket hook with auto-reconnect and REST polling fallback. */

import { useState, useEffect, useRef, useCallback } from "react";

// -- Public types --

export type WebSocketChannel = "market" | "foreign" | "index" | "alerts";
export type ConnectionStatus = "connecting" | "connected" | "disconnected";

export interface WebSocketResult<T> {
  /** Latest parsed message from WebSocket or REST fallback */
  data: T | null;
  /** Current connection status */
  status: ConnectionStatus;
  /** Last error encountered */
  error: Error | null;
  /** true = WebSocket active, false = REST polling fallback */
  isLive: boolean;
  /** Force reconnect — resets attempts and restarts WS connection */
  reconnect: () => void;
}

export interface UseWebSocketOptions<T> {
  /** Auth token appended as ?token= query param */
  token?: string;
  /** REST fetcher for polling fallback when WS unavailable */
  fallbackFetcher?: () => Promise<T>;
  /** Polling interval for fallback mode (ms, default: 5000) */
  fallbackIntervalMs?: number;
  /** Max consecutive reconnect attempts before fallback (default: 3) */
  maxReconnectAttempts?: number;
}

// -- Constants --

const BASE_DELAY_MS = 1_000;
const MAX_DELAY_MS = 30_000;
const DEFAULT_MAX_ATTEMPTS = 3;
const DEFAULT_POLL_INTERVAL = 5_000;
const WS_RETRY_INTERVAL = 30_000;

// -- Hook --

export function useWebSocket<T>(
  channel: WebSocketChannel,
  options: UseWebSocketOptions<T> = {},
): WebSocketResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const [error, setError] = useState<Error | null>(null);
  const [isLive, setIsLive] = useState(true);

  // Keep latest options accessible without re-running effect
  const optsRef = useRef(options);
  optsRef.current = options;

  // Expose reconnect from inside effect via stable ref
  const reconnectRef = useRef<() => void>(() => {});

  const token = options.token;

  useEffect(() => {
    let unmounted = false;
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout>;
    let pollTimer: ReturnType<typeof setInterval>;
    let retryTimer: ReturnType<typeof setInterval>;
    let attempts = 0;
    let inFallback = false;
    let generation = 0; // prevents stale poll responses after WS connects

    const buildUrl = (): string => {
      const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
      let url = `${proto}//${window.location.host}/ws/${channel}`;
      if (token) url += `?token=${encodeURIComponent(token)}`;
      return url;
    };

    const stopFallback = () => {
      inFallback = false;
      clearInterval(pollTimer);
      clearInterval(retryTimer);
    };

    const startFallback = () => {
      const fetcher = optsRef.current.fallbackFetcher;
      if (!fetcher || inFallback) return;
      inFallback = true;
      setIsLive(false);
      setStatus("connected"); // data still flows via REST

      const pollGen = generation;
      const poll = async () => {
        try {
          const result = await fetcher();
          if (!unmounted && generation === pollGen) {
            setData(result);
            setError(null);
          }
        } catch (err) {
          if (!unmounted && generation === pollGen) {
            setError(err instanceof Error ? err : new Error(String(err)));
          }
        }
      };

      poll();
      pollTimer = setInterval(
        poll,
        optsRef.current.fallbackIntervalMs ?? DEFAULT_POLL_INTERVAL,
      );

      // Periodically re-attempt WS while polling
      retryTimer = setInterval(() => {
        if (unmounted) return;
        attempts = 0;
        connect();
      }, WS_RETRY_INTERVAL);
    };

    const connect = () => {
      if (unmounted) return;
      if (!inFallback) setStatus("connecting");

      ws = new WebSocket(buildUrl());

      ws.onopen = () => {
        if (unmounted) return;
        attempts = 0;
        generation += 1; // invalidate in-flight poll responses
        stopFallback();
        setStatus("connected");
        setIsLive(true);
        setError(null);
      };

      ws.onmessage = (e) => {
        if (unmounted) return;
        try {
          const msg = JSON.parse(e.data);
          if (msg?.type === "status") return; // SSI upstream status event
          setData(msg as T);
        } catch {
          // binary or non-JSON — ignore
        }
      };

      ws.onerror = () => {
        if (unmounted) return;
        setError(new Error(`WebSocket error on /ws/${channel}`));
      };

      ws.onclose = () => {
        if (unmounted) return;
        ws = null;
        attempts += 1;

        // If already polling, retryTimer handles next WS attempt
        if (inFallback) return;

        setStatus("disconnected");
        const max = optsRef.current.maxReconnectAttempts ?? DEFAULT_MAX_ATTEMPTS;
        if (attempts >= max) {
          startFallback();
        } else {
          const delay = Math.min(BASE_DELAY_MS * 2 ** attempts, MAX_DELAY_MS);
          reconnectTimer = setTimeout(connect, delay);
        }
      };
    };

    // Expose manual reconnect
    reconnectRef.current = () => {
      attempts = 0;
      clearTimeout(reconnectTimer);
      stopFallback();
      if (ws) {
        ws.onclose = null;
        ws.close();
        ws = null;
      }
      connect();
    };

    connect();

    return () => {
      unmounted = true;
      clearTimeout(reconnectTimer);
      stopFallback();
      if (ws) {
        ws.onclose = null;
        ws.close();
      }
    };
  }, [channel, token]);

  const reconnect = useCallback(() => reconnectRef.current(), []);

  return { data, status, error, isLive, reconnect };
}
