# ai-companion

Monorepo for the AI Companion project, containing the FastAPI backend, Expo mobile app, shared infrastructure, and documentation.

## Quickstart

```bash
# 1. Start the stack (builds images on first run)
docker compose -f infra/compose.yaml up -d

# 2. View logs
docker compose -f infra/compose.yaml logs -f api

# 3. Run backend tests
docker compose -f infra/compose.yaml run --rm api poetry run pytest

# 4. Stop the stack
docker compose -f infra/compose.yaml down
```

Health check: `http://localhost:8000/health` should return `{"status":"ok"}` once the API container is up.

See `docs/` for additional guides and project notes.

## Run Book

```bash
# 1) Clone and boot
make up

# 2) Create DB and run migrations
docker compose -f infra/compose.yaml exec api alembic upgrade head

# 3) Seed personas and a test user
docker compose -f infra/compose.yaml exec api python -m app.scripts.seed

# 4) Hit health and chat
curl localhost:8000/health
curl -X POST localhost:8000/chat -H 'Content-Type: application/json' -d '{"message":"Remind me to drink water at 3pm"}'

# 5) Start mobile (new terminal)
cd mobile && npm install && npx expo start --ios
```

## Chat API Example

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{"message":"Remind me to drink water at 3pm.","persona_key":"coach"}'
```

The endpoint responds with the assistant message and an `actions` array describing any tool calls that were executed (for example, scheduling a reminder).


## Environment Variables

Set the following variables (for both api and worker containers) to enable reminder delivery:

- `RESEND_API_KEY` and `RESEND_FROM_EMAIL` for outbound emails through Resend.
- `EXPO_ACCESS_TOKEN` (and optionally `EXPO_PUSH_URL`) to send Expo push notifications.
- `ENCRYPTION_KEY` (generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REDIRECT_URI` for Google Calendar OAuth.

## Google Calendar OAuth

1. Create OAuth 2.0 credentials (Web application) in Google Cloud Console.
2. Add `http://localhost:8000/oauth/google/callback` as an authorized redirect URI.
3. Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, and `ENCRYPTION_KEY` in your environment.
4. Visit `GET /oauth/google/start` (include `X-API-Key`) to complete consent.
5. After authorizing, `GET /agenda` will return upcoming events and `/chat` (e.g., "Add standup tomorrow 9am") will create calendar entries.

