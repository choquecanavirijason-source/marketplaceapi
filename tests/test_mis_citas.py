"""GET /api/v1/booking/my-appointments y /ws-ticket: identifican a la clienta
en el salón por salon_client_id (con X-Internal-Key) si la cuenta está
vinculada, y siempre mandan el email."""
import pytest

from tests.conftest import INTERNAL_KEY
from tests.test_vinculo_salon import _auth, _customer

MY = "/booking-public/my-appointments"
WS = "/booking-public/ws-ticket"
ROUTES = [("/api/v1/booking/my-appointments", MY), ("/api/v1/booking/ws-ticket", WS)]


@pytest.mark.parametrize("route,salon_path", ROUTES)
def test_vinculada_manda_id_clave_y_email(client, salon, db_session, route, salon_path):
    customer = _customer(db_session, salon_client_id=5)

    r = client.get(route, headers=_auth(customer))

    assert r.status_code == 200
    call = salon.gets(salon_path)[-1]
    assert call["params"] == {"email": "ana@x.com", "salon_client_id": 5}
    assert call["headers"]["X-Internal-Key"] == INTERNAL_KEY


@pytest.mark.parametrize("route,salon_path", ROUTES)
def test_sin_vincular_solo_email_sin_clave(client, salon, db_session, route, salon_path):
    customer = _customer(db_session)
    salon.client_id_by_email = {"ana@x.com": 3}

    r = client.get(route, headers=_auth(customer))

    assert r.status_code == 200
    call = salon.gets(salon_path)[-1]
    assert call["params"] == {"email": "ana@x.com"}
    assert "X-Internal-Key" not in call["headers"]
    # Estas rutas no intentan vincular: se cargan seguido.
    assert "/clients/link-marketplace" not in salon.paths()


@pytest.mark.parametrize("route,salon_path", ROUTES)
def test_sin_clave_interna_solo_email(client, salon, db_session, monkeypatch, route, salon_path):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "internal_api_key", "")
    customer = _customer(db_session, salon_client_id=5)
    salon.client_id_by_email = {"ana@x.com": 5}

    r = client.get(route, headers=_auth(customer))

    assert r.status_code == 200
    assert salon.gets(salon_path)[-1]["params"] == {"email": "ana@x.com"}


def test_mis_citas_usa_la_ficha_vinculada_aunque_el_email_sea_otro(client, salon, db_session):
    # Vinculada por teléfono a la ficha 5; por email el salón no la encuentra.
    customer = _customer(db_session, salon_client_id=5)

    r = client.get("/api/v1/booking/my-appointments", headers=_auth(customer))

    assert r.json() == [{"id": 1, "client_id": 5}]


def test_ws_ticket_devuelve_la_respuesta_del_salon(client, salon, db_session):
    customer = _customer(db_session, salon_client_id=5)

    r = client.get("/api/v1/booking/ws-ticket", headers=_auth(customer))

    assert r.json() == {"client_id": 5, "token": "ws-token"}


@pytest.mark.parametrize("route,salon_path", ROUTES)
def test_ficha_borrada_desvincula_y_reintenta_por_email(client, salon, db_session, route, salon_path):
    customer = _customer(db_session, salon_client_id=5)
    salon.deleted_client_ids = {5}
    salon.client_id_by_email = {"ana@x.com": 8}
    salon.link = {"status": "not_found"}

    r = client.get(route, headers=_auth(customer))

    assert r.status_code == 200
    calls = salon.gets(salon_path)
    assert len(calls) == 2
    assert calls[1]["params"] == {"email": "ana@x.com"}
    assert customer.salon_client_id is None


def test_ficha_borrada_se_revincula_si_el_salon_encuentra_otra(client, salon, db_session):
    customer = _customer(db_session, salon_client_id=5)
    salon.deleted_client_ids = {5}
    salon.link = {"status": "found", "id": 6}

    r = client.get("/api/v1/booking/ws-ticket", headers=_auth(customer))

    assert r.json() == {"client_id": 6, "token": "ws-token"}
    assert salon.gets(WS)[-1]["params"]["salon_client_id"] == 6
    assert customer.salon_client_id == 6


def test_salon_antiguo_no_pierde_el_vinculo(client, salon, db_session):
    # Salón sin soporte de salon_client_id en GET: busca por email, no la
    # encuentra y responde 404. El vínculo se revalida y se conserva.
    customer = _customer(db_session, salon_client_id=5)
    salon.get_supports_client_id = False
    salon.link = {"status": "found", "id": 5}

    r = client.get("/api/v1/booking/ws-ticket", headers=_auth(customer))

    assert r.status_code == 404
    assert customer.salon_client_id == 5


def test_ws_ticket_sin_ficha_es_404(client, salon, db_session):
    customer = _customer(db_session)

    r = client.get("/api/v1/booking/ws-ticket", headers=_auth(customer))

    assert r.status_code == 404
    assert r.json()["detail"] == "Cliente no encontrado"
    assert len(salon.gets(WS)) == 1


@pytest.mark.parametrize("route", [r for r, _ in ROUTES])
def test_salon_caido_es_503(client, salon, db_session, route):
    customer = _customer(db_session, salon_client_id=5)
    salon.down = True

    r = client.get(route, headers=_auth(customer))

    assert r.status_code == 503
    assert customer.salon_client_id == 5


@pytest.mark.parametrize("route", [r for r, _ in ROUTES])
def test_exige_sesion(client, route):
    assert client.get(route).status_code == 401
