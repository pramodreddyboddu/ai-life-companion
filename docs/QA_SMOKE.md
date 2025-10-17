# QA Smoke Checklist

Follow this script to validate the production (or staging) environment end-to-end. Each step should be marked pass/fail and linked to a bug if it fails.

> **Prep**
> - Set `BASE_URL` to the deployed API (e.g., `https://ai-companion-api-...onrender.com`).
> - Obtain an active API key (`X-API-Key`).
> - Note the time zone used for reminders (America/Chicago by default).

## 1. Chat ? Reminder Creation
1. `curl -X POST $BASE_URL/chat -H "Content-Type: application/json" -H "X-API-Key: <API_KEY>" -d '{"message":"Remind me to drink water in 2 minutes","persona_key":"accountability"}'`
2. Verify response HTTP 200.
3. Response body includes:
   - `assistant_message` confirming the reminder.
   - `actions[0].tool == "schedule_reminder"`.
   - `actions[0].result.run_ts` is in the future.

## 2. Reminder Fires
1. Wait 2–3 minutes after scheduling.
2. Check notification channel(s):
   - If email is configured, confirm email delivered.
   - If push (Expo) is configured, confirm push notification.
3. Alternatively, query the database (`reminders.status`) to confirm it transitions to `sent` with `sent_at` populated.

## 3. Calendar Sync (Optional)
1. Ensure Google OAuth is connected for the test user (`GET /oauth/google/start`).
2. `curl -X POST $BASE_URL/calendar/add -H "Content-Type: application/json" -H "X-API-Key: <API_KEY>" -d '{"reminder_id":"<UUID>","duration_minutes":30}'`
3. Expect response `{ "status": "created", "event_id": "..." }`.
4. Verify the event appears in Google Calendar within 1 minute.
5. `curl $BASE_URL/calendar/list` should include the new event.

## 4. Cancel Reminder Flow
1. Create a reminder with a longer delay (e.g., 15 minutes).
2. Capture the reminder ID from the `schedule_reminder` action.
3. `curl -X POST $BASE_URL/reminders/<REMINDER_ID>/cancel -H "X-API-Key: <API_KEY>"`
4. Expect response `{ "status": "canceled" }`.
5. Verify DB `status == canceled` and no reminder fires.

## 5. Rate Limit (429)
1. Rapidly send >10 requests within a minute:
   ```bash
   for i in {1..12}; do
     curl -s -o /dev/null -w "%{http_code}\n" \
       -X POST $BASE_URL/chat \
       -H "Content-Type: application/json" \
       -H "X-API-Key: <API_KEY>" \
       -d '{"message":"Ping"}'
   done
   ```
2. Confirm the loop returns at least one `429` with body `{ "error": "rate_limited", "retry_after_seconds": N }`.

## 6. Metrics Endpoint
1. `curl $BASE_URL/metrics/basic`
2. Ensure HTTP 200 and counters include `reminder_scheduled`, `reminder_sent`, `reminder_canceled`, `reminder_error`.
3. Values should increment after actions above (allow for Redis propagation).

## 7. Health Endpoint
1. `curl $BASE_URL/healthz`
2. Expect response `{ "db": "ok", "redis": "ok", "celery": "ok" }`.
3. If Celery workers are intentionally offline, confirm `celery` reports fail reason.

## 8. Mobile Chat Round-trip
1. Launch the Expo app (or staging build).
2. Configure the API key and base URL in settings/storage.
3. Send a chat message from the mobile UI.
4. Verify assistant message appears and tool actions (chips) render.


## 9. Admin Dashboard (Optional)
- Optionally toggle a feature flag via `/admin/features` to ensure runtime gating works.
1. Ensure `ADMIN_API_KEY` is configured and saved in the web Settings page.
2. Visit `/admin` in the web dashboard; verify queue depth, worker heartbeat, and recent reminders load.
3. Hit `GET /admin/queues` with `X-Admin-Token` header to confirm CLI access.
## 9. Smoke Script (Optional, Local)
1. Run `./scripts/smoke.sh` in the repo root.
2. Confirm script exits 0 and prints `Smoke test completed successfully.`

Document pass/fail status and attach evidence (screenshots, logs) in the release QA ticket.

- Optional: scrape `/metrics` or `/metrics/basic` for Prometheus-compatible output.
