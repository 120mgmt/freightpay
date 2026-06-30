const API_BASE = import.meta.env.VITE_API_URL || "";

export async function apiFetch(path: string, options: RequestInit = {}) {
  const token = localStorage.getItem("lh_token");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return fetch(`${API_BASE}${path}`, { ...options, headers });
}
