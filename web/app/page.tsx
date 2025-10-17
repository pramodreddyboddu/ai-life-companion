"use client";

import { FormEvent, useState } from "react";
import { apiRequest } from "../lib/api";
import { loadSettings } from "../lib/config";

type ChatAction = {
  tool: string;
  params?: Record<string, unknown> | null;
  result?: Record<string, unknown> | null;
};

type ChatResponse = {
  assistant_message: string;
  actions: ChatAction[];
};

export default function ChatPage() {
  const [message, setMessage] = useState("");
  const [assistantMessage, setAssistantMessage] = useState<string | null>(null);
  const [actions, setActions] = useState<ChatAction[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const settings = loadSettings();

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setAssistantMessage(null);
    setActions([]);

    if (!settings.apiKey) {
      setError("Add your API key in Settings first.");
      return;
    }

    try {
      setIsLoading(true);
      const response = await apiRequest<ChatResponse>("/chat", {
        method: "POST",
        body: JSON.stringify({ message, persona_key: "accountability" }),
      });
      setAssistantMessage(response.assistant_message);
      setActions(response.actions || []);
      setMessage("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div>
      <h1>Chat</h1>
      <p>Send a prompt to the Accountability persona and view actions returned.</p>

      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "1rem" }}>
        <textarea
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          rows={4}
          placeholder="Remind me to drink water every afternoon..."
          required
        />
        <button type="submit" disabled={isLoading}>
          {isLoading ? "Sending..." : "Send"}
        </button>
      </form>

      {error && <p style={{ color: "#dc2626", marginTop: "1rem" }}>{error}</p>}

      {assistantMessage && (
        <div style={{ marginTop: "1.5rem" }}>
          <h2>Assistant</h2>
          <p>{assistantMessage}</p>
        </div>
      )}

      {actions.length > 0 && (
        <div style={{ marginTop: "1.5rem" }}>
          <h2>Actions</h2>
          <ul>
            {actions.map((action, index) => (
              <li key={`${action.tool}-${index}`}>
                <strong>{action.tool}</strong>
                <pre style={{ whiteSpace: "pre-wrap", background: "#f3f4f6", padding: "0.5rem", borderRadius: "0.5rem" }}>
{JSON.stringify(action, null, 2)}
                </pre>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

