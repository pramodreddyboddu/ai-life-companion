# Privacy & PII Redaction Policy

This document summarizes how AI Companion handles user data, what information is stored, and how sensitive fields are masked.

## Data Classification

| Category | Examples | Stored? | Retention |
| --- | --- | --- | --- |
| User identifiers | Email, user ID (UUID) | Yes | 90 days (rolling) |
| Reminders | Reminder text, timestamps | Yes | 90 days (rolling) |
| Calendar events | Google event ID, start/end times | Yes | 90 days (rolling) |
| API credentials | Encrypted refresh tokens | Yes (encrypted) | Until user revokes |
| Raw audio/files | STT uploads | No (deleted immediately after transcription) |
| Chat transcripts | Assistant messages, actions | Yes | 30 days (rolling) |

## Redaction Rules

Logs and analytics data must redact personally identifiable information before storage:

| Pattern | Masked Example |
| --- | --- |
| Email addresses | `[REDACTED_EMAIL]` |
| Phone numbers | `[REDACTED_PHONE]` |
| Secrets / tokens (e.g., `sk-...`) | `[REDACTED_TOKEN]` |

Any additional tokens or API keys printed by third-party libraries should be filtered by the logging layer or replaced via `redact_pii`.

## Logging Policy

1. **Structured JSON logs**: Include explicit fields (correlation IDs, reminder IDs) but never raw user text or contact details.
2. **Fail-fast configuration**: Logs note missing env vars without printing values.
3. **Reminder text** is only logged after redaction.
4. **Celery tasks** log statuses with masked user info.

## Retention

- Reminder records: 90 days; periodic clean-up job purges older rows (planned).
- Logs: 30 days max (`log retention` per environment).
- Metrics counters: aggregated; no PII stored.
- Audio uploads: deleted after STT completion.

## Access

- Only authorized on-call engineers can view admin endpoints (`/admin/*`) with an `ADMIN_API_KEY`.
- Prep environments mirror prod data retention to reduce drift.

## User Requests

- Deletion requests: Remove user record + reminders + tokens.
- Data export requests: Provide reminders and chat history within 30 days.

## Open Items

- Automate reminder cleanup job (currently manual).
- Expand PII regexes for international formats.
