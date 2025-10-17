from httpx import ASGITransport, AsyncClient
import pytest

from app.api.deps import get_db_session
from app.api.routers import health as health_router
from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_healthz_endpoint(monkeypatch) -> None:
    async def _fake_session():
        class _Session:
            def execute(self, *_args, **_kwargs):
                return None

        yield _Session()

    app.dependency_overrides[get_db_session] = _fake_session
    monkeypatch.setattr(health_router, "_check_db", lambda session: "ok")
    monkeypatch.setattr(health_router, "_check_redis", lambda: "ok")
    monkeypatch.setattr(health_router, "_check_celery", lambda: "fail: down")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")

    app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 200
    assert response.json() == {"db": "ok", "redis": "ok", "celery": "fail: down"}
