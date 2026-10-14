// Small fetch wrapper for the FastAPI backend.
const BASE = `${import.meta.env.VITE_API_URL || ""}/api`;
const TOKEN_KEY = "c4.token";
const LAST_STUDENT_KEY = "c4.lastStudentId";

function storageGet(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function storageSet(key, value) {
  try {
    if (value == null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // Storage can be blocked (private mode); the app still works for this tab.
  }
}

export const getToken = () => storageGet(TOKEN_KEY);
export const setToken = (token) => storageSet(TOKEN_KEY, token);

// The student last opened, used by the Dashboard and Recommendations menu items.
export const getLastStudentId = () => storageGet(LAST_STUDENT_KEY);
export const setLastStudentId = (id) => storageSet(LAST_STUDENT_KEY, id);

let handleUnauthorized = () => {};
export function setUnauthorizedHandler(fn) {
  handleUnauthorized = fn;
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

function errorMessage(data, status) {
  const detail = data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => `${(d.loc || []).slice(1).join(" › ")}: ${d.msg}`).join("; ");
  }
  return `Request failed (${status}).`;
}

export async function api(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(`${BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("Cannot reach the backend. Make sure it is running on port 8000.", 0);
  }

  const data = await response.json().catch(() => null);
  if (response.status === 401 && path !== "/auth/login") handleUnauthorized();
  if (!response.ok && data === null && response.status >= 500) {
    // The dev proxy answers 500 with no JSON when the backend is down or still starting.
    throw new ApiError("The backend is not responding. Make sure it is running on port 8000, then try again.", response.status);
  }
  if (!response.ok) throw new ApiError(errorMessage(data, response.status), response.status);
  return data;
}
