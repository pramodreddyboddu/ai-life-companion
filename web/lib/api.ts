"use client";

import { loadSettings } from "./config";

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const settings = loadSettings();
  const baseUrl = settings.apiBaseUrl.replace(/\/$/, "");
  const url = path.startsWith("http") ? path : `${baseUrl}${path.startsWith("/") ? path : `/${path}`}`;

  const headers = new Headers(init?.headers || {});
  headers.set("Content-Type", "application/json");
  if (settings.apiKey) {
    headers.set("X-API-Key", settings.apiKey);
  }

  const response = await fetch(url, {
    ...init,
    headers,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with status ${response.status}`);
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return (await response.json()) as T;
  }
  // @ts-expect-error allow other types
  return response;
}

