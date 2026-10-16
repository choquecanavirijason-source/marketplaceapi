"""Vínculo cuenta del marketplace ↔ ficha del salón (salon_client_id) en
registro, login, reserva y POST /api/v1/auth/device."""
from app.domain.entities.customer import Customer
from app.presentation.controllers.auth_controller import _create_token, _hash

from tests.conftest import INTERNAL_KEY

DEVICE = {"installation_id": "install-abc-123", "platform": "android"}
BOOKING = {"service_ids": [1], "branch_id": 2, "start_iso": "2030-01-10T10:00:00"}


def _customer(db, salon_client_id=None, email="ana@x.com", phone="70012345", password="secreta"):
    customer = Customer(
        name="Ana",
        email=email,
        phone=phone,
        hashed_pw=_hash(password),
        source="app",
        salon_client_id=salon_client_id,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def _auth(customer):
    return {"Authorization": f"Bearer {_create_token(customer.id)}"}


def _login(client, **extra):
    return client.post("/api/v1/auth/login", json={"email": "ana@x.com", "password": "secreta", **extra})


# ── Login ─────────────────────────────────────────────────────────────────────

def test_login_vincula_y_devuelve_device_token(client, salon, db_session):
    customer = _customer(db_session)
    salon.link = {"status": "found", "id": 5}

    r = _login(client, **DEVICE)

    assert r.status_code == 200
    assert r.json()["device_token"] == "device-token-123"
    assert customer.salon_client_id == 5
    link = salon.last("/clients/link-marketplace")
    assert link["json"] == {"email": "ana@x.com", "phone": "70012345"}
    assert link["headers"]["X-Internal-Key"] == INTERNAL_KEY
    assert salon.last("/dispositivos")["json"]["client_id"] == 5


def test_login_ambiguous_no_vincula(client, salon, db_session):
    customer = _customer(db_session)
    salon.link = {"status": "ambiguous"}

    r = _login(client, **DEVICE)

    assert r.status_code == 200
    assert r.json()["device_token"] is None
    assert customer.salon_client_id is None
    assert "/dispositivos" not in salon.paths()


def test_login_no_consulta_el_salon_si_ya_esta_vinculada(client, salon, db_session):
    _customer(db_session, salon_client_id=9)

    r = _login(client, **DEVICE)

    assert r.json()["device_token"] == "device-token-123"
    assert "/clients/link-marketplace" not in salon.paths()


def test_login_no_falla_si_el_salon_no_responde(client, salon, db_session):
    customer = _customer(db_session)
    salon.down = True

    r = _login(client, **DEVICE)

    assert r.status_code == 200
    assert r.json()["device_token"] is None
    assert customer.salon_client_id is None


def test_sin_clave_interna_no_se_llama_a_link(client, salon, db_session, monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "internal_api_key", "")
    _customer(db_session)

    r = _login(client, **DEVICE)

    assert r.status_code == 200
    assert salon.calls == []


# ── Registro ──────────────────────────────────────────────────────────────────

def test_register_vincula_y_devuelve_device_token(client, salon, db_session):
    salon.link = {"status": "found", "id": 5}

    r = client.post(
        "/api/v1/auth/register",
        json={"name": "Ana", "email": "ana@x.com", "password": "secreta", **DEVICE},
    )

    assert r.status_code == 201
    assert r.json()["device_token"] == "device-token-123"
    assert db_session.query(Customer).one().salon_client_id == 5


def test_register_not_found_queda_sin_vincular(client, salon, db_session):
    r = client.post(
        "/api/v1/auth/register",
        json={"name": "Ana", "email": "ana@x.com", "password": "secreta", **DEVICE},
    )

    assert r.status_code == 201
    assert r.json()["device_token"] is None
    assert db_session.query(Customer).one().salon_client_id is None
    # Sin teléfono en el registro se manda null, no "".
    assert salon.last("/clients/link-marketplace")["json"] == {"email": "ana@x.com", "phone": None}


# ── Reserva ───────────────────────────────────────────────────────────────────

def test_reserva_manda_salon_client_id_con_clave(client, salon, db_session):
    customer = _customer(db_session, salon_client_id=5)

    r = client.post("/api/v1/booking/appointments", json=BOOKING, headers=_auth(customer))

    assert r.status_code == 201
    call = salon.last("/booking-public/appointments")
    assert call["json"]["salon_client_id"] == 5
    assert call["headers"]["X-Internal-Key"] == INTERNAL_KEY


def test_reserva_not_found_guarda_la_ficha_creada_por_el_salon(client, salon, db_session):
    customer = _customer(db_session)
    salon.booking_client_id = 77

    r = client.post("/api/v1/booking/appointments", json=BOOKING, headers=_auth(customer))

    assert r.status_code == 201
    call = salon.last("/booking-public/appointments")
    assert "salon_client_id" not in call["json"]
    assert "X-Internal-Key" not in call["headers"]
    assert customer.salon_client_id == 77


def test_reserva_ambiguous_no_guarda_client_id(client, salon, db_session):
    customer = _customer(db_session)
    salon.link = {"status": "ambiguous"}

    r = client.post("/api/v1/booking/appointments", json=BOOKING, headers=_auth(customer))

    assert r.status_code == 201
    assert customer.salon_client_id is None


def test_reserva_vincula_antes_de_reservar(client, salon, db_session):
    customer = _customer(db_session)
    salon.link = {"status": "found", "id": 5}

    r = client.post("/api/v1/booking/appointments", json=BOOKING, headers=_auth(customer))

    assert r.status_code == 201
    assert salon.last("/booking-public/appointments")["json"]["salon_client_id"] == 5
    assert customer.salon_client_id == 5


def test_reserva_con_ficha_borrada_en_el_salon_se_desvincula_y_reintenta(client, salon, db_session):
    customer = _customer(db_session, salon_client_id=5)
    salon.deleted_client_ids = {5}
    salon.booking_client_id = 88

    r = client.post("/api/v1/booking/appointments", json=BOOKING, headers=_auth(customer))

    assert r.status_code == 201
    bookings = [c for c in salon.calls if c["path"] == "/booking-public/appointments"]
    assert len(bookings) == 2
    assert "salon_client_id" not in bookings[1]["json"]
    assert customer.salon_client_id == 88


def test_reserva_sin_clave_interna_no_manda_salon_client_id(client, salon, db_session, monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "internal_api_key", "")
    customer = _customer(db_session, salon_client_id=5)

    r = client.post("/api/v1/booking/appointments", json=BOOKING, headers=_auth(customer))

    assert r.status_code == 201
    assert "salon_client_id" not in salon.last("/booking-public/appointments")["json"]


# ── POST /api/v1/auth/device ──────────────────────────────────────────────────

def test_device_vinculada_devuelve_token(client, salon, db_session):
    customer = _customer(db_session, salon_client_id=5)

    r = client.post("/api/v1/auth/device", json=DEVICE, headers=_auth(customer))

    assert r.status_code == 200
    assert r.json() == {"device_token": "device-token-123", "linked": True}
    assert salon.last("/dispositivos")["json"] == {
        "client_id": 5,
        "installation_id": "install-abc-123",
        "platform": "android",
    }


def test_device_intenta_vincular(client, salon, db_session):
    customer = _customer(db_session)
    salon.link = {"status": "found", "id": 5}

    r = client.post("/api/v1/auth/device", json=DEVICE, headers=_auth(customer))

    assert r.json() == {"device_token": "device-token-123", "linked": True}
    assert customer.salon_client_id == 5


def test_device_sin_vincular(client, salon, db_session):
    customer = _customer(db_session)

    r = client.post("/api/v1/auth/device", json=DEVICE, headers=_auth(customer))

    assert r.status_code == 200
    assert r.json() == {"device_token": None, "linked": False}
    assert "/dispositivos" not in salon.paths()


def test_device_vinculada_pero_salon_caido(client, salon, db_session):
    customer = _customer(db_session, salon_client_id=5)
    salon.down = True

    r = client.post("/api/v1/auth/device", json=DEVICE, headers=_auth(customer))

    assert r.status_code == 200
    assert r.json() == {"device_token": None, "linked": True}


def test_device_exige_sesion(client):
    r = client.post("/api/v1/auth/device", json=DEVICE)
    assert r.status_code == 401


def test_device_valida_body(client, db_session):
    customer = _customer(db_session, salon_client_id=5)
    headers = _auth(customer)

    assert client.post(
        "/api/v1/auth/device", json={"installation_id": "corto", "platform": "android"}, headers=headers
    ).status_code == 422
    assert client.post(
        "/api/v1/auth/device", json={"installation_id": "install-abc-123", "platform": "web"}, headers=headers
    ).status_code == 422
