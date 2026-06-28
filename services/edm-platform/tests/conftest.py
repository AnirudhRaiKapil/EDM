import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app import rate_limit
    from app.config import settings
    from app.database import Base, get_db
    from app.main import app
    from app.modules.storage import adapter as storage_adapter

    # Same module-level-singleton problem as the scheduler below: TestClient requests
    # all share one fixed client IP, so without resetting between tests, attempts from
    # every earlier test accumulate and eventually trip the limiter for unrelated tests.
    rate_limit.reset()

    # Settings is a module-level singleton created at first import (whenever that happens
    # to be -- e.g. some test module's top-level imports during pytest's collection phase,
    # before any fixture runs), so monkeypatch.setenv() here is too late for anything read
    # off `settings`; mutate the already-constructed settings object's attributes directly
    # instead. (32+ bytes on the secret specifically to avoid PyJWT's
    # InsecureKeyLengthWarning -- a short test secret is otherwise harmless, but a clean
    # test run is a better signal than one full of warnings that look like they need
    # investigating.)
    monkeypatch.setattr(settings, "jwt_secret", "test-secret-at-least-32-bytes-long-ok")
    # The real APScheduler BackgroundScheduler is a module-level singleton (app/scheduler.py)
    # that would otherwise start once per test process via the lifespan below and accumulate
    # stale jobs across tests, each pointed at a different test's now-gone SQLite DB.
    monkeypatch.setattr(settings, "enable_scheduler", False)

    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    original_storage_root = storage_adapter.storage.root
    storage_adapter.storage.root = tmp_path / "data"

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    storage_adapter.storage.root = original_storage_root
