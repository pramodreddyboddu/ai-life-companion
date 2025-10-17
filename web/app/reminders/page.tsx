"use client";

import { useCallback, useEffect, useState } from "react";
import { apiRequest } from "../../lib/api";
import { loadSettings } from "../../lib/config";

type Reminder = {
  id: string;
  text: string;
  status: string;
  run_ts?: string | null;
  local_ts?: string | null;
  utc_ts?: string | null;
  sent_at?: string | null;
  calendar_event_id?: string | null;
};

type CancelResponse = { status: string; message?: string | null };

export default function RemindersPage() {
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const settings = loadSettings();

  const fetchReminders = useCallback(async () => {
    if (!settings.apiKey) {
      setError("Add your API key in Settings first.");
      return;
    }
    try {
      setIsLoading(true);
      setError(null);
      const data = await apiRequest<Reminder[]>("/reminders");
      setReminders(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsLoading(false);
    }
  }, [settings.apiKey]);

  useEffect(() => {
    fetchReminders();
  }, [fetchReminders]);

  async function handleCancel(reminderId: string) {
    try {
      await apiRequest<CancelResponse>(`/reminders/${reminderId}/cancel`, { method: "POST" });
      fetchReminders();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <div>
      <h1>Reminders</h1>
      <p>View and manage recent reminders.</p>
      <button onClick={fetchReminders} disabled={isLoading} style={{ marginTop: "1rem" }}>
        {isLoading ? "Refreshing..." : "Refresh"}
      </button>

      {error && <p style={{ color: "#dc2626", marginTop: "1rem" }}>{error}</p>}

      <ul style={{ listStyle: "none", padding: 0, marginTop: "1rem", display: "flex", flexDirection: "column", gap: "1rem" }}>
        {reminders.map((reminder) => (
          <li key={reminder.id} style={{ border: "1px solid #e5e7eb", borderRadius: "0.75rem", padding: "1rem", background: "#f9fafb" }}>
            <h3 style={{ marginTop: 0 }}>{reminder.text}</h3>
            <p>Status: <strong>{reminder.status}</strong></p>
            {reminder.utc_ts && <p>Scheduled (UTC): {new Date(reminder.utc_ts).toLocaleString()}</p>}
            {reminder.sent_at && <p>Sent: {new Date(reminder.sent_at).toLocaleString()}</p>}
            {reminder.calendar_event_id && <p>Calendar Event: {reminder.calendar_event_id}</p>}

            {reminder.status === "scheduled" && (
              <button onClick={() => handleCancel(reminder.id)} style={{ marginTop: "0.5rem" }}>
                Cancel
              </button>
            )}
          </li>
        ))}
      </ul>

      {reminders.length === 0 && !isLoading && !error && <p>No reminders yet.</p>}
    </div>
  );
}

