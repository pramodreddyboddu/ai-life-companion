import Constants from "expo-constants";

import { useAppStore } from "../store/useAppStore";

const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL ??
  (Constants.expoConfig?.extra as { apiBaseUrl?: string } | undefined)?.apiBaseUrl ??
  "http://localhost:8000";

export const getApiBaseUrl = () => API_BASE_URL;

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

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers
  });

  if (!response.ok) {
    const message = await response.text();
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
