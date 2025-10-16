#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE="docker compose -f infra/compose.yaml"

cleanup() {
  set +e
  $COMPOSE down --remove-orphans >/dev/null 2>&1
}
trap cleanup EXIT

cd "$ROOT_DIR"

cleanup

echo "[smoke] Booting stack..."
make up

echo "[smoke] Waiting for API container..."
for _ in {1..30}; do
  if $COMPOSE exec api true >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "[smoke] Running unit tests..."
$COMPOSE run --rm api poetry run pytest

echo "[smoke] Applying migrations..."
$COMPOSE exec api alembic upgrade head

echo "[smoke] Seeding baseline data..."
$COMPOSE exec api python -m app.scripts.seed

echo "[smoke] Executing mocked chat flow..."
$COMPOSE exec api python -m app.scripts.mock_chat

echo "[smoke] Smoke test completed successfully."
