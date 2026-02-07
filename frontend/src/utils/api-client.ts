/** Thin fetch wrapper for backend API calls. */

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

export async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json() as Promise<T>;
}
