import os
import sys
import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import validate_test_database_separation


def _test_database_url() -> str:
    """Select a test-only database without hard-coding a Docker hostname."""
    configured_url = os.getenv("TEST_DATABASE_URL")
    if configured_url:
        production_url = os.getenv("DATABASE_URL")
        if production_url:
            validate_test_database_separation(production_url, configured_url)
        return configured_url

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("DATABASE_URL="):
                    database_url = line.split("=", 1)[1]
                    break
    if not database_url:
        raise RuntimeError("Set TEST_DATABASE_URL before running backend tests.")

    url = make_url(database_url)
    # The checked-in Docker configuration names the database host "postgres".
    # When the suite is launched on the Windows host, Compose publishes that
    # service on localhost instead. Explicit TEST_DATABASE_URL still overrides
    # this portability fallback above.
    if os.name == "nt" and url.host == "postgres":
        url = url.set(host="localhost")
    test_name = f"{url.database}_test" if not url.database.endswith("_test") else url.database
    return str(url.set(database=test_name))


# The application creates its SQLAlchemy engine at import time. Configure it
# first, prioritising TEST_DATABASE_URL when the caller explicitly supplies it.
os.environ["DATABASE_URL"] = _test_database_url()

from app.main import app
from app.database import engine
from app.models import Base


async def _prepare_test_schema():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    # TestClient owns a different event loop on Windows. Do not carry pooled
    # asyncpg connections from this setup loop into the application lifespan.
    await engine.dispose()


async def _clean_test_schema():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="module")
def client():
    asyncio.run(_prepare_test_schema())
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        asyncio.run(_clean_test_schema())


@pytest.fixture
def auth_headers(client):
    email = "testuser@example.com"
    password = "testpass123"

    client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "full_name": "Test User"},
    )
    response = client.post(
        "/api/auth/login",
        data={"username": email, "password": password},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
