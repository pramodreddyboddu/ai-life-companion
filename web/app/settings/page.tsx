"use client";

import { FormEvent, useState } from "react";
import { loadSettings, saveSettings } from "../../lib/config";

export default function SettingsPage() {
  const current = loadSettings();
  const [apiKey, setApiKey] = useState(current.apiKey);
  const [apiBaseUrl, setApiBaseUrl] = useState(current.apiBaseUrl);
  const [timezone, setTimezone] = useState(current.timezone);
  const [adminToken, setAdminToken] = useState(current.adminToken);
  const [saved, setSaved] = useState(false);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    saveSettings({ apiKey, apiBaseUrl, timezone, adminToken });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <div>
      <h1>Settings</h1>
      <p>Configure API access and defaults for this browser.</p>

      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem", marginTop: "1.5rem" }}>
        <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
          <span>API Base URL</span>
          <input type="url" value={apiBaseUrl} onChange={(event) => setApiBaseUrl(event.target.value)} required />
        </label>

        <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
          <span>API Key</span>
          <input type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} required />
        </label>

        <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
          <span>Timezone</span>
          <input value={timezone} onChange={(event) => setTimezone(event.target.value)} />
        </label>

        <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
          <span>Admin Token (for /admin endpoints)</span>
          <input type="password" value={adminToken} onChange={(event) => setAdminToken(event.target.value)} />
        </label>

        <button type="submit">Save Settings</button>
        {saved && <span style={{ color: "#16a34a" }}>Saved!</span>}
      </form>
    </div>
  );
}
