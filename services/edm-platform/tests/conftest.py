import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")

    from fastapi.testclient import TestClient

    from app.database import Base, get_db
    from app.main import app
    from app.modules.storage import adapter as storage_adapter

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
