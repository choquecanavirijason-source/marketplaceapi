"""
Fixtures comunes. Los tests no tocan PostgreSQL ni el salón real:
- Base de datos: SQLite en memoria con solo la tabla mp_customers.
- Salón (elashesbackend): httpx.post reemplazado por FakeSalon, que responde
  según la ruta y guarda cada llamada para revisarla.
"""
import importlib
import pkgutil

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config.settings import settings
from app.core import rate_limit
from app.core.dependencies import get_db
from app.domain.entities.customer import Customer
from app.presentation.controllers.auth_controller import router as auth_router
from app.presentation.controllers.booking_controller import router as booking_router
import app.domain.entities as entities

# Las relaciones entre modelos se resuelven por nombre ("Product"…): todos los
# modelos tienen que estar importados antes de usar cualquiera.
for _mod in pkgutil.iter_modules(entities.__path__):
    importlib.import_module(f"{entities.__name__}.{_mod.name}")

INTERNAL_KEY = "test-internal-key"


class FakeSalon:
    """Respuestas configurables de elashesbackend, por ruta."""

    def __init__(self):
        self.calls: list[dict] = []
        self.link = {"status": "not_found"}
        self.device_token = "device-token-123"
        self.booking_client_id = 77
        # Ids de ficha que el salón ya no tiene (POST /booking-public/appointments → 404).
        self.deleted_client_ids: set[int] = set()
        self.verify_login = None  # None = CI inválido
        self.down = False

    def post(self, url, json=None, headers=None, timeout=None, **_):
        path = url.split("://", 1)[-1].split("/", 1)[-1]
        path = "/" + path
        self.calls.append({"path": path, "json": json, "headers": headers or {}})
        if self.down:
            raise httpx.ConnectError("salón caído")
        request = httpx.Request("POST", url)
        if path == "/clients/link-marketplace":
            return httpx.Response(200, json=self.link, request=request)
        if path == "/dispositivos":
            return httpx.Response(201, json={"token": self.device_token}, request=request)
        if path == "/clients/verify-salon-login":
            return httpx.Response(200, json=self.verify_login or {"valid": False}, request=request)
        if path == "/booking-public/appointments":
            salon_client_id = (json or {}).get("salon_client_id")
            if salon_client_id is not None:
                if (headers or {}).get("X-Internal-Key") != INTERNAL_KEY:
                    return httpx.Response(401, json={"detail": "Clave interna inválida"}, request=request)
                if salon_client_id in self.deleted_client_ids:
                    return httpx.Response(404, json={"detail": "Cliente no encontrado"}, request=request)
                client_id = salon_client_id
            else:
                client_id = self.booking_client_id
            return httpx.Response(
                201, json={"id": 1, "status": "pending", "client_id": client_id}, request=request
            )
        return httpx.Response(404, json={"detail": "Not Found"}, request=request)

    def paths(self) -> list[str]:
        return [c["path"] for c in self.calls]

    def last(self, path: str) -> dict:
        return [c for c in self.calls if c["path"] == path][-1]


@pytest.fixture
def salon(monkeypatch):
    fake = FakeSalon()
    monkeypatch.setattr(httpx, "post", fake.post)
    monkeypatch.setattr(settings, "internal_api_key", INTERNAL_KEY)
    return fake


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Customer.__table__.create(engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def client(db_session, salon):
    rate_limit._attempts.clear()
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(booking_router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)
