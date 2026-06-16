export type ApiResponse<T> = {
  success: boolean;
  message: string;
  data: T;
  detail?: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:5000/api";

function authHeaders(): HeadersInit {
  if (typeof window === "undefined") return {};
  const userId = window.localStorage.getItem("currentUserId");
  return userId ? { "X-User-Id": userId } : {};
}

async function parseResponse<T>(response: Response): Promise<T> {
  const payload = (await response.json()) as ApiResponse<T>;
  if (!response.ok || !payload.success) {
    throw new Error(payload.detail || payload.message || "请求失败");
  }
  return payload.data;
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { cache: "no-store", headers: authHeaders() });
  return parseResponse<T>(response);
}

export async function apiSend<T>(path: string, method: "POST" | "PUT" | "DELETE", body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json", ...authHeaders() } : authHeaders(),
    body: body ? JSON.stringify(body) : undefined
  });
  return parseResponse<T>(response);
}
