export type ApiState<T> = {
  loading: boolean;
  data: T | null;
  error: string | null;
};

export type ApiError = {
  message: string;
  status?: number;
  authRequired: boolean;
};

export const DEFAULT_API_BASE = "http://127.0.0.1:8765";

export function getApiBase(): string {
  return localStorage.getItem("LIUANT_DESKTOP_API_BASE") || DEFAULT_API_BASE;
}

export function setApiBase(value: string): void {
  localStorage.setItem("LIUANT_DESKTOP_API_BASE", value.replace(/\/$/, ""));
}

export function getAuthToken(): string {
  return localStorage.getItem("LIUANT_API_TOKEN") || "";
}

export function setAuthToken(value: string): void {
  if (value) {
    localStorage.setItem("LIUANT_API_TOKEN", value);
  } else {
    clearAuthToken();
  }
}

export function clearAuthToken(): void {
  localStorage.removeItem("LIUANT_API_TOKEN");
  localStorage.removeItem("LIUANT_SESSION_TOKEN");
}

export function sanitizeError(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  return message.replace(/Bearer\s+[A-Za-z0-9._~+/=-]+/gi, "Bearer [redacted]").replace(/token=[^&\s]+/gi, "token=[redacted]");
}

async function parseResponse<T>(path: string, response: Response): Promise<T> {
  if (!response.ok) {
    const authRequired = response.status === 401;
    const error = new Error(`${path} returned ${response.status}${authRequired ? " auth required" : ""}`) as Error & ApiError;
    error.status = response.status;
    error.authRequired = authRequired;
    throw error;
  }
  return response.json() as Promise<T>;
}

export async function apiGet<T>(path: string): Promise<T> {
  const headers: HeadersInit = {};
  const token = getAuthToken();
  const session = localStorage.getItem("LIUANT_SESSION_TOKEN");
  if (token) headers.Authorization = `Bearer ${token}`;
  if (session) headers["X-Liuant-Session"] = session;

  const response = await fetch(`${getApiBase()}${path}`, { headers });
  return parseResponse<T>(path, response);
}

export async function apiPost<T>(path: string, body: unknown = {}): Promise<T> {
  const token = getAuthToken();
  const session = localStorage.getItem("LIUANT_SESSION_TOKEN");
  const response = await fetch(`${getApiBase()}${path}`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(session ? { "X-Liuant-Session": session } : {})
    },
    body: JSON.stringify(body)
  });
  return parseResponse<T>(path, response);
}
