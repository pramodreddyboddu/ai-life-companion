"use client";

import { useCallback, useEffect, useState } from "react";
import { apiRequest } from "../../lib/api";
import { loadSettings } from "../../lib/config";

function formatJSON(value: unknown) {
  return JSON.stringify(value, null, 2);
}

type QueueStatus = { queue: string; depth: number };

type WorkerStatus = { status: string; details: unknown };

type FeatureFlagSummary = {
  key: string;
  enabled: boolean;
  effective: boolean;
  override: boolean | null;
  description?: string | null;
};

type ReminderSummary = {
  id: string;
  user_id: string;
  text: string;
  status: string;
  utc_ts?: string | null;
  sent_at?: string | null;
  calendar_event_id?: string | null;
};

export default function AdminPage() {
  const settings = loadSettings();
  const [queue, setQueue] = useState<QueueStatus | null>(null);
  const [workers, setWorkers] = useState<WorkerStatus | null>(null);
  const [reminders, setReminders] = useState<ReminderSummary[]>([]);
  const [flags, setFlags] = useState<FeatureFlagSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchAll = useCallback(async () => {
    if (!settings.adminToken) {
      setError("Add an admin token in Settings to view this page.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const headers = { "X-Admin-Token": settings.adminToken };
      const [queueResp, workersResp, remindersResp, flagsResp] = await Promise.all([
        apiRequest<QueueStatus>("/admin/queues", { headers }),
        apiRequest<WorkerStatus>("/admin/workers", { headers }),
        apiRequest<ReminderSummary[]>("/admin/reminders", { headers }),
        apiRequest<FeatureFlagSummary[]>("/admin/features", { headers }),
      ]);
      setQueue(queueResp);
      setWorkers(workersResp);
      setReminders(remindersResp);
      setFlags(flagsResp);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [settings.adminToken]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  async function toggleFlag(key: string, enabled: boolean) {
    try {
      const headers = {
        "X-Admin-Token": settings.adminToken,
      };
      await apiRequest(`/admin/features`, {
        method: "POST",
        headers,
        body: JSON.stringify({ key, enabled }),
      });
      fetchAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <div>
      <h1>Admin Dashboard</h1>
      <p>Operational snapshots require a valid admin token.</p>
      <button onClick={fetchAll} disabled={loading} style={{ marginTop: "1rem" }}>
        {loading ? "Refreshing..." : "Refresh"}
      </button>

      {error && <p style={{ color: "#dc2626", marginTop: "1rem" }}>{error}</p>}

      {queue && (
        <section style={{ marginTop: "1.5rem" }}>
          <h2>Queue Depth</h2>
          <pre style={{ background: "#f3f4f6", padding: "0.75rem", borderRadius: "0.75rem" }}>{formatJSON(queue)}</pre>
        </section>
      )}

      {workers && (
        <section style={{ marginTop: "1.5rem" }}>
          <h2>Worker Heartbeat</h2>
          <pre style={{ background: "#f3f4f6", padding: "0.75rem", borderRadius: "0.75rem" }}>{formatJSON(workers)}</pre>
        </section>
      )}

      {flags.length > 0 && (
        <section style={{ marginTop: "1.5rem" }}>
          <h2>Feature Flags</h2>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th align="left">Key</th>
                <th align="left">Effective</th>
                <th align="left">Override</th>
                <th align="left">Actions</th>
              </tr>
            </thead>
            <tbody>
              {flags.map((flag) => (
                <tr key={flag.key} style={{ borderTop: "1px solid #e5e7eb" }}>
                  <td>{flag.key}</td>
                  <td>{flag.effective ? "on" : "off"}</td>
                  <td>{flag.override === null ? "-" : String(flag.override)}</td>
                  <td>
                    <button onClick={() => toggleFlag(flag.key, !flag.enabled)}>
                      Set {flag.enabled ? "Off" : "On"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {reminders.length > 0 && (
        <section style={{ marginTop: "1.5rem" }}>
          <h2>Recent Reminders</h2>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th align="left">Text</th>
                <th align="left">Status</th>
                <th align="left">UTC</th>
                <th align="left">Sent</th>
              </tr>
            </thead>
            <tbody>
              {reminders.map((reminder) => (
                <tr key={reminder.id} style={{ borderTop: "1px solid #e5e7eb" }}>
                  <td>{reminder.text}</td>
                  <td>{reminder.status}</td>
                  <td>{reminder.utc_ts ? new Date(reminder.utc_ts).toLocaleString() : "-"}</td>
                  <td>{reminder.sent_at ? new Date(reminder.sent_at).toLocaleString() : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
