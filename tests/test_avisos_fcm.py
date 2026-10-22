"""
Proxy del token FCM: PUT/DELETE /api/v1/avisos/dispositivo/fcm-token reenvían
a PUT/DELETE /dispositivos/actual/fcm-token de elashesbackend con el mismo
Authorization (device_token). Aquí no se guarda ni se registra el token.
"""
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.presentation.controllers.avisos_controller import router as avisos_router

URL = "/api/v1/avisos/dispositivo/fcm-token"
AUTH = {"Authorization": "Bearer device-token-123"}
FCM_TOKEN = "fcm-token-" + "x" * 150


class FakeSalonRequests:
    """httpx.request del salón: responde con el status configurado y guarda la llamada."""

    def __init__(self):
        self.calls: list[dict] = []
        self.status = 204
        self.body = None
        self.down = False

    def __call__(self, method, url, headers=None, json=None, timeout=None, **_):
        self.calls.append({"method": method, "url": url, "headers": headers or {}, "json": json})
        if self.down:
            raise httpx.ConnectError("salón caído")
        request = httpx.Request(method, url)
        if self.body is None:
            return httpx.Response(self.status, request=request)
        return httpx.Response(self.status, json=self.body, request=request)


@pytest.fixture
def salon(monkeypatch):
    fake = FakeSalonRequests()
    monkeypatch.setattr(httpx, "request", fake)
    return fake


@pytest.fixture
def client(salon):
    app = FastAPI()
    app.include_router(avisos_router)
    return TestClient(app)


class TestRegistrar:
    def test_exito_reenvia_token_y_authorization(self, client, salon):
        resp = client.put(URL, json={"fcm_token": FCM_TOKEN}, headers=AUTH)
        assert resp.status_code == 204
        [call] = salon.calls
        assert call["method"] == "PUT"
        assert call["url"].endswith("/dispositivos/actual/fcm-token")
        assert call["headers"] == {"Authorization": "Bearer device-token-123"}
        assert call["json"] == {"fcm_token": FCM_TOKEN}

    def test_error_del_salon_se_propaga(self, client, salon):
        salon.status, salon.body = 401, {"detail": "Token de dispositivo inválido o revocado"}
        resp = client.put(URL, json={"fcm_token": FCM_TOKEN}, headers=AUTH)
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Token de dispositivo inválido o revocado"

    def test_validacion_del_salon_se_propaga(self, client, salon):
        salon.status, salon.body = 422, {"detail": "token inválido"}
        assert client.put(URL, json={"fcm_token": "corto"}, headers=AUTH).status_code == 422

    def test_salon_caido_503(self, client, salon):
        salon.down = True
        assert client.put(URL, json={"fcm_token": FCM_TOKEN}, headers=AUTH).status_code == 503

    def test_sin_autenticacion_401_sin_llamar_al_salon(self, client, salon):
        assert client.put(URL, json={"fcm_token": FCM_TOKEN}).status_code == 401
        assert client.put(URL, json={"fcm_token": FCM_TOKEN},
                          headers={"Authorization": "Basic abc"}).status_code == 401
        assert salon.calls == []

    def test_cuerpo_invalido_422_sin_llamar_al_salon(self, client, salon):
        assert client.put(URL, json={"fcm_token": 123}, headers=AUTH).status_code == 422
        assert client.put(URL, json={}, headers=AUTH).status_code == 422
        assert salon.calls == []


class TestBorrar:
    def test_exito(self, client, salon):
        assert client.delete(URL, headers=AUTH).status_code == 204
        [call] = salon.calls
        assert call["method"] == "DELETE"
        assert call["url"].endswith("/dispositivos/actual/fcm-token")
        assert call["headers"] == {"Authorization": "Bearer device-token-123"}

    @pytest.mark.parametrize("status", [401, 404])
    def test_nada_que_borrar_no_falla(self, client, salon, status):
        salon.status, salon.body = status, {"detail": "x"}
        assert client.delete(URL, headers=AUTH).status_code == 204

    def test_error_del_salon_se_propaga(self, client, salon):
        salon.status, salon.body = 500, {"detail": "Error interno"}
        assert client.delete(URL, headers=AUTH).status_code == 500

    def test_sin_autenticacion_401_sin_llamar_al_salon(self, client, salon):
        assert client.delete(URL).status_code == 401
        assert salon.calls == []
