/** Generic polling hook — fetches data at a configurable interval. */

import { useState, useEffect, useCallback, useRef } from "react";

interface PollingResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  refresh: () => void;
}

export function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs: number = 5000,
): PollingResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const fetcherRef = useRef(fetcher);
  const inFlightRef = useRef(false);

  fetcherRef.current = fetcher;

  const doFetch = useCallback(async () => {
    if (inFlightRef.current) return; // skip if previous still running
    inFlightRef.current = true;
    try {
      const result = await fetcherRef.current();
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      inFlightRef.current = false;
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    doFetch();
    const id = setInterval(doFetch, intervalMs);
    return () => clearInterval(id);
  }, [doFetch, intervalMs]);

  return { data, loading, error, refresh: doFetch };
}
