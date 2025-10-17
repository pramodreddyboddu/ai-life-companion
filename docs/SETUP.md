# Local Development Setup

Follow these steps to go from a fresh clone to a working AI Companion stack.

## Prerequisites

- Docker Desktop 4.x (or Docker Engine with Compose v2)
- GNU Make (optional but recommended)
- Bash-compatible shell (for the smoke script)

## 1. Clone and configure environment

```bash
git clone https://github.com/your-org/ai-companion.git
cd ai-companion

# Populate API env variables for local Compose runs
cp api/sample.env api/.env
```

Edit `api/.env` as needed. The defaults target the services defined in `infra/compose.yaml`. Replace placeholder secrets such as `OPENAI_API_KEY`, `SECRET_KEY`, and `ENCRYPTION_KEY` before going live.

## 2. Validate configuration

Run the configuration check to ensure all required environment variables are present. The command exits with a clear error message if anything is missing.

```bash
docker compose -f infra/compose.yaml run --rm api \
  poetry run python -c "from app.settings import settings; print('configuration ok')"
```

If the command exits non-zero, review the logged `configuration_validation_failed` message, update your environment file, and rerun the check before continuing.

## 3. Start the local stack

```bash
docker compose -f infra/compose.yaml up -d
docker compose -f infra/compose.yaml logs -f api
```

Wait until the API container reports `INFO  Running on http://0.0.0.0:8000`.

## 4. Apply migrations and seed demo data

```bash
docker compose -f infra/compose.yaml exec api alembic upgrade head
docker compose -f infra/compose.yaml exec api python -m app.scripts.seed
```

The seed script prints a `DEMO_API_KEY=...` value you can use to call the API. By default this is `sk-demo-accountability`.

## 5. Run the smoke test (optional but recommended)

```bash
./scripts/smoke.sh
```

This script boots the stack, runs migrations, seeds data, and exercises the chat endpoint via a mocked flow.

## 6. Verify health and chat endpoints

```bash
# Readiness check (DB, Redis, Celery)
curl http://localhost:8000/healthz

# Chat request (replace API key if you changed it)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk-demo-accountability" \
  -d '{"message":"Remind me to drink water at 3pm","persona_key":"accountability"}'
```

You should see an assistant response plus a `schedule_reminder` action in the JSON payload.

## 7. Run the full test suite

```bash
make test
```

`make test` launches isolated Postgres/Redis containers, runs migrations, executes `pytest`, and tears everything down when finished.

## 8. Stop the stack

```bash
docker compose -f infra/compose.yaml down
```

The project is now ready for local iteration. For deployment-specific variables, review `infra/render.env.example`.

## 9. Optional: Configure Google Calendar OAuth

1. Create OAuth 2.0 Client (Web) in Google Cloud Console.
2. Set authorized redirect URI to match `GOOGLE_REDIRECT_URI` (default `http://localhost:8000/oauth/google/callback`).
3. Update `api/.env` with `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REDIRECT_URI`.
4. Restart the API container after updating env vars.
5. Connect a user by hitting `GET /oauth/google/start` (include `X-API-Key`).
6. After consent, verify `/calendar/list` returns events and `/calendar/add` can create reminders as calendar events.

## 10. Voice Features (Optional)

- `/stt` accepts audio uploads (`.m4a`, `.mp3`, `.wav`, `.ogg`) up to 10 MB and transcribes using Whisper.
- `/tts` accepts JSON `{ "text": "...", "language": "en" }` and returns an MP3 stream generated with gTTS.
- Voice features require the user to be on the PRO plan; ensure the seeded user or test user has `plan = pro`.

## 11. Admin Observability (Optional)

- Set an `ADMIN_API_KEY` in `api/.env` for secured admin endpoints.
- `/admin/queues`, `/admin/workers`, `/admin/reminders` require `X-Admin-Token` header.
- The web dashboard (`/admin`) uses the token stored in Settings to display queue depth, worker heartbeat, and recent reminders.

## 12. Feature Flags

- Flags stored in `feature_flags` table; use `/admin/features` to list and POST to toggle.
- Supported keys: `voice_mode`, `calendar_integration`, `multi_channel_notifications`.
- Environment overrides: set `FEATURE_FLAG_<KEY>=true|false` (e.g., `FEATURE_FLAG_VOICE_MODE=false`) for emergency toggles.
- Changes take effect within 30 seconds due to caching.
