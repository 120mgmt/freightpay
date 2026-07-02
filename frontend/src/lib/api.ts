const API_BASE = import.meta.env.VITE_API_URL || "";

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...extra,
  };
  const token = localStorage.getItem("lh_token");
  if (token) headers["Authorization"] = `Bearer ${token}`;
  try {
    const user = JSON.parse(localStorage.getItem("lh_user") || "null");
    if (user?.company_id) headers["X-Company-Id"] = String(user.company_id);
  } catch {
    /* corrupt lh_user — ignore */
  }
  return headers;
}

/** Record clickwrap legal acceptance (shown at sign-in/registration) and signal retry. */
async function acceptLegal(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/auth/legal/accept`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ accepted_tos: true, accepted_privacy: true, accepted_refund: true }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function apiFetch(path: string, options: RequestInit = {}) {
  const doFetch = () =>
    fetch(`${API_BASE}${path}`, {
      ...options,
      headers: authHeaders((options.headers as Record<string, string>) || {}),
    });

  let res = await doFetch();

  // Accounts created before legal acceptance was recorded get blocked on every
  // endpoint — accept (consent is displayed at sign-in) and retry once.
  if (res.status === 403) {
    const clone = res.clone();
    try {
      const body = await clone.json();
      if (body?.error === "LEGAL_NOT_ACCEPTED" && (await acceptLegal())) {
        res = await doFetch();
      }
    } catch {
      /* non-JSON 403 — fall through */
    }
  }

  // Expired/invalid token → send the user back to sign-in.
  if (res.status === 401 && localStorage.getItem("lh_token")) {
    localStorage.removeItem("lh_token");
    localStorage.removeItem("lh_user");
    sessionStorage.setItem("lh_redirect", window.location.pathname);
    window.location.href = "/signin";
  }

  return res;
}
