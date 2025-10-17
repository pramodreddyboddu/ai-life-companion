# Incident Runbook

This runbook guides on-call engineers through common production incidents.

## Quick References
- **API Base:** `https://ai-companion-api-…`
- **Render Dashboard:** `https://dashboard.render.com`
- **Logs:** Render logs (API, worker, beat), plus `/metrics/basic`.
- **Smoke Script:** `./scripts/smoke.sh` (local verification).

## Common Incidents

### 1. Worker Down (Celery Worker)
1. Check Render dashboard ? `ai-companion-worker`.
2. Inspect logs for process exits.
3. Restart service: click **Manual Deploy ? Clear build cache ? Deploy**.
4. Verify `/healthz` shows `celery: ok` and reminders resume.
5. If queues backed up:
   - `docker compose -f infra/compose.yaml exec api python -m app.tasks.reminders.send_due_reminders`
   - Monitor `/metrics/basic` for increasing `reminder_sent`.

### 2. Beat Down (Scheduler)
1. Render service `ai-companion-beat`.
2. Restart if not running.
3. Inspect logs for cron errors (missing ENV?). Fix config.
4. If beat is down for longer than the recurrence window, manually queue reminders:
   - `docker compose -f infra/compose.yaml exec api poetry run celery -A app.celery_app call app.tasks.reminders.send_due_reminders`

### 3. Database Down
1. Confirm Render Postgres status or RDS.
2. Review alerts (Render, Cloud provider).
3. Restart database or failover if applicable.
4. After DB restored:
   - Run migrations (`alembic upgrade head`).
   - Requeue reminders (`python -m app.tasks.reminders.send_due_reminders`).

### 4. Redis Down
1. Check Render Redis instance.
2. Restart service; verify `PING -> PONG`.
3. Workers may need restart to reconnect.
4. Review failure logs (rate limiter errors, Celery backend).

## Rollback Procedure
1. Determine last-known-good commit.
2. Deploy via Render **Manual Deploy** with commit hash.
3. Verify `/healthz` and chat smoke test.
4. Communicate rollback in incident channel/postmortem.

## Requeue Reminders
- Use the Celery task to re-scan due reminders:
  ```bash
  docker compose -f infra/compose.yaml exec api poetry run celery -A app.celery_app call app.tasks.reminders.send_due_reminders
  ```
- For targeted reminders, modify the script or schedule to queue specific IDs.

## Logs & Metrics Queries
- API logs: `curl -X POST /chat` failure traces, look for 5xx patterns.
- Reminder metrics: `/metrics/basic` counters (`reminder_*`).
- Health: `/healthz` to check DB/Redis/Celery.
- Celery logs: search for `Retrying reminder` / `failed after max retries`.

## Post-Incident
1. Update incident ticket with timeline, root cause, mitigation.
2. Review error budget impact (see `docs/SLOs.md`).
3. Schedule retro within 48 hours if SLOs breached.
