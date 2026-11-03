"""Pruebas de seguridad de la API de validación. No necesitan PostgreSQL: la conexión se simula."""
from contextlib import contextmanager
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import api.main as main
import api.security as security

CLAVE = "clave-de-prueba-suficientemente-larga"


class FakeCursor:
    def __init__(self, store):
        self.store = store

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.store["queries"].append((sql, params))

    def fetchall(self):
        return []

    def fetchone(self):
        return {"id": "x", "question": "¿Hacen envíos?", "status": "approved"}


@pytest.fixture
def client(monkeypatch):
    store = {"queries": []}

    @contextmanager
    def fake_conn():
        class Conn:
            def cursor(self, **kwargs):
                return FakeCursor(store)
        yield Conn()

    monkeypatch.setattr(security, "API_KEY", CLAVE)
    monkeypatch.setattr(main, "get_conn", fake_conn)
    c = TestClient(main.app)
    c.store = store
    return c


def test_health_es_publico(client):
    assert client.get("/health").status_code == 200


@pytest.mark.parametrize("ruta", ["/suggestions", "/suggestions/stats", f"/suggestions/{uuid4()}"])
def test_rutas_protegidas_exigen_api_key(client, ruta):
    assert client.get(ruta).status_code == 401
    assert client.get(ruta, headers={"X-API-Key": "clave-incorrecta"}).status_code == 401
    assert client.get(ruta, headers={"X-API-Key": CLAVE}).status_code != 401


def test_no_se_puede_aprobar_sin_api_key(client):
    res = client.post(f"/suggestions/{uuid4()}/approve", json={})
    assert res.status_code == 401
    assert client.store["queries"] == []


def test_sin_api_key_configurada_la_api_no_atiende(client, monkeypatch):
    monkeypatch.setattr(security, "API_KEY", None)
    assert client.get("/suggestions", headers={"X-API-Key": ""}).status_code == 503


def test_rechaza_estados_desconocidos(client):
    res = client.get("/suggestions", params={"status": "approved' OR '1'='1"}, headers={"X-API-Key": CLAVE})
    assert res.status_code == 422
    assert client.store["queries"] == []


def test_rechaza_ids_que_no_son_uuid(client):
    res = client.post("/suggestions/1;DROP TABLE faq_suggestions/approve", json={}, headers={"X-API-Key": CLAVE})
    assert res.status_code in (404, 422)
    assert client.store["queries"] == []


def test_aprobar_usa_consulta_parametrizada(client):
    sid = uuid4()
    res = client.post(f"/suggestions/{sid}/approve", json={"reviewed_by": "leo"}, headers={"X-API-Key": CLAVE})
    assert res.status_code == 200
    sql, params = client.store["queries"][-1]
    assert str(sid) not in sql
    assert params == ("approved", "leo", str(sid))
