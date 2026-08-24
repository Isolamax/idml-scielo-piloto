from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from idml_foundation.database import Base, get_db
from idml_foundation.main import create_app
from idml_foundation.settings import Settings, get_settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        database_url="sqlite+pysqlite:///:memory:",
        redis_url="redis://127.0.0.1:6379/15",
        artifact_root=tmp_path / "artifacts",
        session_pepper="test-session-pepper-with-at-least-32-bytes",
    )


@pytest.fixture
def engine() -> Generator[Engine, None, None]:
    database = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(database)
    yield database
    Base.metadata.drop_all(database)
    database.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def db(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    session = session_factory()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def client(
    session_factory: sessionmaker[Session], settings: Settings
) -> Generator[TestClient, None, None]:
    get_settings.cache_clear()
    app = create_app()

    def override_db() -> Generator[Session, None, None]:
        session = session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
