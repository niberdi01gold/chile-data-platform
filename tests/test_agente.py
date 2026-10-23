"""Pruebas del agente SIN llamar a ninguna IA: herramientas, calificador y ciclo de herramientas.

Corren gratis y en segundos, en tu PC y en la CI.
"""

import duckdb
import pytest
from google.genai import types

from agente import herramientas
from agente.agente import AgenteGemini
from evals.calificar import calificar, numeros_en


@pytest.fixture(autouse=True)
def base_de_prueba(tmp_path, monkeypatch):
    """Base chica con datos conocidos; las herramientas la usan en vez de la real."""
    ruta = tmp_path / "prueba.duckdb"
    con = duckdb.connect(str(ruta))
    con.execute("""
        create table resumen_indicadores as select * from (values
            ('dolar', 'Dólar observado', 'Pesos', date '2026-10-21', 980.0, '%', 1.0, 2.0),
            ('tpm', 'TPM', 'Porcentaje', date '2026-10-21', 4.5, 'puntos', 0.0, -0.25)
        ) t(indicador, nombre, unidad_medida, fecha_ultimo_valor, ultimo_valor,
            tipo_variacion, variacion_30d, variacion_12m)
    """)
    con.execute("""
        create table historico_indicadores as select * from (values
            ('dolar', date '2026-01-02', 900.0),
            ('dolar', date '2026-06-01', 1000.0),
            ('dolar', date '2026-10-21', 980.0),
            ('tpm', date '2026-01-02', 5.0),
            ('tpm', date '2026-10-21', 4.5)
        ) t(indicador, fecha, valor)
    """)
    con.close()
    monkeypatch.setenv("RUTA_BD", str(ruta))


# ---------------------------------------------------------------- Herramientas
def test_variacion_en_porcentaje_para_montos():
    r = herramientas.calcular_variacion("dolar", "2026-01-01")
    assert r["tipo_variacion"] == "%"
    assert r["variacion"] == pytest.approx(8.89, abs=0.01)    # 900 → 980


def test_variacion_en_puntos_para_porcentajes():
    r = herramientas.calcular_variacion("tpm", "2026-01-01")
    assert (r["variacion"], r["tipo_variacion"]) == (-0.5, "puntos")


def test_serie_entrega_maximo_y_minimo():
    r = herramientas.obtener_serie("dolar")
    assert r["maximo"]["valor"] == 1000.0 and r["minimo"]["valor"] == 900.0


def test_indicador_inexistente_no_rompe_el_agente():
    assert "error" in herramientas.ejecutar("obtener_serie", {"codigo": "bitcoin"})


# ---------------------------------------------------------------- Calificador
def test_lee_numeros_en_formato_chileno_y_anglosajon():
    assert 41194.55 in numeros_en("La UF está en $41.194,55 hoy")
    assert 978.56 in numeros_en("USD/CLP 978.56")


def test_aprueba_cifra_correcta_y_reprueba_invencion():
    caso = {"esperado": lambda: 980.0}
    usadas = [{"herramienta": "listar_indicadores"}]
    assert calificar(caso, "El dólar está en $980,00", usadas)[0]
    assert not calificar(caso, "El dólar está en $950", usadas)[0]
    assert not calificar(caso, "El dólar está en $980", [])[0]        # sin herramientas = sospechoso


def test_fuera_de_alcance():
    caso = {"fuera_de_alcance": True}
    assert calificar(caso, "No tengo datos del bitcoin.", [])[0]
    assert not calificar(caso, "El bitcoin vale 60.000 dólares.", [])[0]


# ---------------------------------------------------------------- Ciclo del agente (IA simulada)
class ModeloFalso:
    """Simula a Gemini: primero pide una herramienta, después responde con texto."""

    def __init__(self):
        self.vueltas = 0

    def generate_content(self, model, contents, config):
        self.vueltas += 1
        if self.vueltas == 1:
            parte = types.Part(function_call=types.FunctionCall(
                name="calcular_variacion", args={"codigo": "dolar", "desde": "2026-01-01"}))
        else:
            parte = types.Part(text="El dólar subió 8,89 % desde el 2 de enero.")
        return types.GenerateContentResponse(
            candidates=[types.Candidate(content=types.Content(role="model", parts=[parte]))])


class ClienteFalso:
    def __init__(self):
        self.models = ModeloFalso()


def test_ciclo_ejecuta_la_herramienta_y_devuelve_la_respuesta():
    texto, llamadas = AgenteGemini(cliente=ClienteFalso()).responder("¿Cuánto subió el dólar este año?")
    assert llamadas == [{"herramienta": "calcular_variacion",
                         "argumentos": {"codigo": "dolar", "desde": "2026-01-01"}}]
    assert "8,89" in texto
