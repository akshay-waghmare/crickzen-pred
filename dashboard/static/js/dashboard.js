/**
 * CrickenZen Dashboard — shared client utilities
 */

/**
 * Fetch wrapper with auth + JSON handling.
 * @param {string} path - API path (e.g., '/auth/login')
 * @param {object} opts - { method, token, body }
 */
async function czFetch(path, opts = {}) {
  const { method = "GET", token, body } = opts;
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const config = { method, headers };
  if (body && method !== "GET") config.body = JSON.stringify(body);

  const resp = await fetch(path, config);
  const data = await resp.json().catch(() => null);

  if (!resp.ok) {
    const msg = data?.detail || `Request failed (${resp.status})`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

/**
 * Auto-refresh JWT before expiry.
 * Call once on page load.
 */
function setupTokenRefresh() {
  const REFRESH_INTERVAL = 50 * 60 * 1000; // 50 minutes
  setInterval(async () => {
    const refreshToken = localStorage.getItem("cz_refresh");
    if (!refreshToken) return;
    try {
      const data = await czFetch("/auth/refresh", {
        method: "POST",
        body: { refresh_token: refreshToken },
      });
      localStorage.setItem("cz_token", data.access_token);
      localStorage.setItem("cz_refresh", data.refresh_token);
    } catch {
      // Refresh failed — user will need to re-login
      localStorage.removeItem("cz_token");
      localStorage.removeItem("cz_refresh");
      window.location.href = "/login";
    }
  }, REFRESH_INTERVAL);
}

// Start auto-refresh on load
setupTokenRefresh();
