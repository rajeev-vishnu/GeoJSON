const ACCESS_KEY = "access";
const REFRESH_KEY = "refresh";

const REFRESH_URL = "/api/auth/refresh/";
const ME_URL = "/api/auth/me/";

function readToken(key) {
  return localStorage.getItem(key);
}

function writeTokens(access, refresh) {
  if (access) localStorage.setItem(ACCESS_KEY, access);
  if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
}

function clearTokens() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

async function refreshAccessToken() {
  const refresh = readToken(REFRESH_KEY);
  if (!refresh) {
    clearTokens();
    return null;
  }
  const response = await fetch(REFRESH_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });
  if (!response.ok) {
    clearTokens();
    return null;
  }
  const body = await response.json();
  writeTokens(body.access, body.refresh);
  return body.access;
}

async function request(path, options = {}, { retried = false } = {}) {
  const headers = new Headers(options.headers || {});
  const access = readToken(ACCESS_KEY);
  if (access) headers.set("Authorization", `Bearer ${access}`);
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(path, { ...options, headers });
  if (response.status !== 401 || retried) {
    return response;
  }
  const newAccess = await refreshAccessToken();
  if (!newAccess) {
    return response;
  }
  const retryHeaders = new Headers(headers);
  retryHeaders.set("Authorization", `Bearer ${newAccess}`);
  return request(path, { ...options, headers: retryHeaders }, { retried: true });
}

async function getJson(path) {
  const response = await request(path, { method: "GET" });
  if (!response.ok) {
    throw new Error(`GET ${path} failed: ${response.status}`);
  }
  return response.json();
}

async function sendJson(path, method, body) {
  const response = await request(path, {
    method,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    let detail = `${method} ${path} failed: ${response.status}`;
    try {
      const errorBody = await response.json();
      detail = JSON.stringify(errorBody);
    } catch (_parseError) {
      // ignore: response had no JSON body
    }
    throw new Error(detail);
  }
  if (response.status === 204) return null;
  return response.json();
}

export const api = {
  get: (path) => getJson(path),
  post: (path, body) => sendJson(path, "POST", body),
  patch: (path, body) => sendJson(path, "PATCH", body),
  put: (path, body) => sendJson(path, "PUT", body),
  delete: (path) => sendJson(path, "DELETE"),
  me: () => getJson(ME_URL),
  hasAccessToken: () => Boolean(readToken(ACCESS_KEY)),
  clearTokens,
};
