"""Casos de evaluación del agente.

Cada caso tiene una pregunta y una función que calcula la respuesta correcta DIRECTAMENTE desde
la base de datos (sin IA). Así la "respuesta correcta" se actualiza sola cada día con los datos.
"""

from agente.herramientas import calcular_variacion, listar_indicadores, obtener_serie


def ultimo(codigo):
    for ind in listar_indicadores()["indicadores"]:
        if ind["indicador"] == codigo:
            return ind["ultimo_valor"]
    raise ValueError(codigo)


CASOS = [
    # --- Último valor ---
    {"id": "dolar_hoy", "pregunta": "¿Cuál es el valor del dólar hoy?",
     "esperado": lambda: ultimo("dolar")},
    {"id": "uf_hoy", "pregunta": "¿A cuánto está la UF?",
     "esperado": lambda: ultimo("uf")},
    {"id": "euro_hoy", "pregunta": "¿Cuánto vale el euro en pesos chilenos?",
     "esperado": lambda: ultimo("euro")},
    {"id": "tpm_hoy", "pregunta": "¿Cuál es la tasa de política monetaria actual?",
     "esperado": lambda: ultimo("tpm")},
    {"id": "ipc_ultimo", "pregunta": "¿Cuál fue la última variación mensual del IPC?",
     "esperado": lambda: ultimo("ipc")},
    {"id": "desempleo", "pregunta": "¿Cuál es la tasa de desempleo más reciente en Chile?",
     "esperado": lambda: ultimo("tasa_desempleo")},
    # --- Variaciones (requieren elegir bien la herramienta y las fechas) ---
    {"id": "dolar_2026", "pregunta": "¿Cuánto ha variado el dólar desde el 1 de enero de 2026?",
     "esperado": lambda: calcular_variacion("dolar", "2026-01-01")["variacion"],
     "herramienta": "calcular_variacion"},
    {"id": "uf_2026", "pregunta": "¿Cuánto ha subido la UF en lo que va de 2026, en porcentaje?",
     "esperado": lambda: calcular_variacion("uf", "2026-01-01")["variacion"],
     "herramienta": "calcular_variacion"},
    {"id": "tpm_puntos", "pregunta": "¿Cuántos puntos ha cambiado la TPM desde el 1 de enero de 2025?",
     "esperado": lambda: calcular_variacion("tpm", "2025-01-01")["variacion"],
     "herramienta": "calcular_variacion"},
    # --- Máximos y mínimos ---
    {"id": "dolar_max_2025", "pregunta": "¿Cuál fue el valor más alto del dólar durante 2025?",
     "esperado": lambda: obtener_serie("dolar", "2025-01-01", "2025-12-31")["maximo"]["valor"],
     "herramienta": "obtener_serie"},
    {"id": "cobre_min_2024", "pregunta": "¿Cuál fue el precio mínimo del cobre en 2024?",
     "esperado": lambda: obtener_serie("libra_cobre", "2024-01-01", "2024-12-31")["minimo"]["valor"],
     "herramienta": "obtener_serie"},
    # --- Fuera de alcance: el agente debe reconocer que no tiene el dato, sin inventar ---
    {"id": "bitcoin", "pregunta": "¿Cuál es el precio del bitcoin hoy?",
     "fuera_de_alcance": True},
    {"id": "dolar_argentina", "pregunta": "¿A cuánto está el dólar blue en Argentina?",
     "fuera_de_alcance": True},
]
