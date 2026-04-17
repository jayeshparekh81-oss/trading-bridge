const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

interface ApiOptions extends RequestInit {
  token?: string;
}

class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(status: number, message: string, data?: unknown) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

async function api<T>(endpoint: string, options: ApiOptions = {}): Promise<T> {
  const { token, ...fetchOptions } = options;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE_URL}${endpoint}`, {
    ...fetchOptions,
    headers,
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(
      res.status,
      data.detail || data.message || `HTTP ${res.status}`,
      data
    );
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export const apiClient = {
  get: <T>(url: string, token?: string) =>
    api<T>(url, { method: "GET", token }),

  post: <T>(url: string, body: unknown, token?: string) =>
    api<T>(url, { method: "POST", body: JSON.stringify(body), token }),

  put: <T>(url: string, body: unknown, token?: string) =>
    api<T>(url, { method: "PUT", body: JSON.stringify(body), token }),

  delete: <T>(url: string, token?: string) =>
    api<T>(url, { method: "DELETE", token }),
};

export { ApiError };
