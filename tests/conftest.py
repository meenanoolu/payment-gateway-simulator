import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.main import app, get_db
from fastapi.testclient import TestClient

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture()
def client():
    # StaticPool: keeps a single shared connection alive for the whole
    # in-memory DB. Without it, each new connection from the pool would
    # get its OWN blank :memory: database and "no such table" errors.
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


VALID_CARD = "4111111111111111"  # passes Luhn, standard test card number
INVALID_CARD = "4111111111111112"  # fails Luhn