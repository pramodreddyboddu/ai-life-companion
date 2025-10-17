"use client";

const STORAGE_KEY = "ai-companion-settings";

export type ClientSettings = {
  apiKey: string;
  apiBaseUrl: string;
  timezone: string;
  adminToken: string;
};

const defaultSettings: ClientSettings = {
  apiKey: "",
  apiBaseUrl: "http://localhost:8000",
  timezone: "America/Chicago",
  adminToken: "",
};

export function loadSettings(): ClientSettings {
  if (typeof window === "undefined") {
    return defaultSettings;
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return defaultSettings;
    }
    const parsed = JSON.parse(raw) as ClientSettings;
    return { ...defaultSettings, ...parsed };
  } catch {
    return defaultSettings;
  }
}

export function saveSettings(settings: ClientSettings) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

