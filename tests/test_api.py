"""Pruebas de la API con una base de datos pequeña creada solo para las pruebas.

Uso:
    pytest -v
"""

from datetime import date

import duckdb
import pytest
from fastapi.testclient import TestClient

from api.main import app, obtener_bd


@pytest.fixture
def cliente(tmp_path):
    """Crea una base de prueba con datos conocidos y hace que la API la use."""
    ruta = str(tmp_path / "prueba.duckdb")
    con = duckdb.connect(ruta)
    con.execute("""
        create table resumen_indicadores as select * from (values
            ('dolar', 'Dólar observado', 'Pesos', date '2026-10-16', 950.5, '%', 1.2, 3.4),
            ('tpm', 'Tasa Política Monetaria', 'Porcentaje', date '2026-10-16', 4.75, 'puntos', 0.0, -0.25)
        ) t(indicador, nombre, unidad_medida, fecha_ultimo_valor, ultimo_valor,
            tipo_variacion, variacion_30d, variacion_12m)
    """)
    con.execute("""
        create table historico_indicadores as select * from (values
            ('dolar_2026-10-14', 'dolar', date '2026-10-14', 940.0),
            ('dolar_2026-10-15', 'dolar', date '2026-10-15', 945.0),
            ('dolar_2026-10-16', 'dolar', date '2026-10-16', 950.5)
        ) t(id, indicador, fecha, valor)
    """)
    con.close()

    def bd_de_prueba():
        c = duckdb.connect(ruta, read_only=True)
        try:
            yield c
        finally:
            c.close()

    app.dependency_overrides[obtener_bd] = bd_de_prueba   # reemplaza la base real por la de prueba
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_salud(cliente):
    r = cliente.get("/salud")
    assert r.status_code == 200
    assert r.json() == {"estado": "ok", "indicadores": 2, "ultimo_dato": "2026-10-16"}


def test_listar_indicadores(cliente):
    r = cliente.get("/indicadores")
    assert r.status_code == 200
    assert [i["indicador"] for i in r.json()] == ["dolar", "tpm"]


def test_obtener_indicador(cliente):
    r = cliente.get("/indicadores/dolar")
    assert r.status_code == 200
    assert r.json()["ultimo_valor"] == 950.5


def test_codigo_en_mayusculas(cliente):
    assert cliente.get("/indicadores/DOLAR").status_code == 200


def test_indicador_inexistente_da_404(cliente):
    r = cliente.get("/indicadores/bitcoin")
    assert r.status_code == 404
    assert "no existe" in r.json()["detail"]


def test_serie_completa(cliente):
    r = cliente.get("/indicadores/dolar/serie")
    assert r.status_code == 200
    assert r.json()["cantidad"] == 3


def test_serie_filtrada_por_fechas(cliente):
    r = cliente.get("/indicadores/dolar/serie", params={"desde": "2026-10-15", "hasta": "2026-10-15"})
    assert r.json()["datos"] == [{"fecha": "2026-10-15", "valor": 945.0}]


def test_fechas_invertidas_da_400(cliente):
    r = cliente.get("/indicadores/dolar/serie", params={"desde": "2026-10-16", "hasta": "2026-10-01"})
    assert r.status_code == 400


def test_fecha_mal_escrita_da_422(cliente):
    r = cliente.get("/indicadores/dolar/serie", params={"desde": "ayer"})
    assert r.status_code == 422      # FastAPI valida el formato de la fecha automáticamente
