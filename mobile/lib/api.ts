import { DEFAULT_API_BASE_URL, useAppStore } from "../store/useAppStore";

export const getApiBaseUrl = () => {
  const { apiBaseUrl } = useAppStore.getState();
  return apiBaseUrl || DEFAULT_API_BASE_URL;
};

function buildUrl(path: string): string {
  const base = getApiBaseUrl().replace(/\/+$/, "");
  const normalisedPath = path.startsWith("/") ? path : `/${path}`;
  return `${base}${normalisedPath}`;
}

export async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const { apiKey } = useAppStore.getState();
  const headers = new Headers(options.headers || {});
  if (apiKey) {
    headers.set("X-API-Key", apiKey);
  }

  const body = options.body;
  const isFormData = typeof FormData !== "undefined" && body instanceof FormData;
  if (body && !isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(buildUrl(path), {
    ...options,
    headers
  });

  if (!response.ok) {
    const contentType = response.headers.get("content-type") || "";
    let message: string | undefined;
    if (contentType.includes("application/json")) {
      try {
        const data = await response.json();
        message = data?.detail ?? data?.message;
      } catch (error) {
        message = undefined;
      }
    }
    if (!message) {
      message = await response.text();
    }
    throw new Error(message || `Request failed with status ${response.status}`);
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return (await response.json()) as T;
  }

  // @ts-expect-error allow string responses
  return (await response.text()) as T;
}

export async function postJson<T>(path: string, payload: unknown): Promise<T> {
  return apiRequest<T>(path, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function getJson<T>(path: string): Promise<T> {
  return apiRequest<T>(path, { method: "GET" });
}
