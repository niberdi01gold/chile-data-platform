"""Herramientas del agente: funciones normales de Python que leen la base de datos.

El modelo de IA no sabe el valor del dólar de hoy. Lo que sí sabe es PEDIR que se ejecute
una de estas funciones; nuestro código la ejecuta y le devuelve el resultado.
Son independientes del proveedor de IA (Gemini, Claude...).
"""

import os
import urllib.request
from datetime import date
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parent.parent
DATOS_URL = os.getenv(
    "DATOS_URL",
    "https://github.com/niberdi01gold/chile-data-platform/releases/download/datos/warehouse.duckdb",
)


def ruta_bd():
    return Path(os.getenv("RUTA_BD", RAIZ / "data" / "warehouse.duckdb"))


def conectar():
    """Abre la base en solo lectura. Si no existe, descarga la última publicada."""
    ruta = ruta_bd()
    if not ruta.exists():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(DATOS_URL, ruta)
    return duckdb.connect(str(ruta), read_only=True)


def _filas(con, sql, params=()):
    resultado = con.execute(sql, list(params))
    columnas = [c[0] for c in resultado.description]
    return [dict(zip(columnas, f)) for f in resultado.fetchall()]


def _unidad(con, codigo):
    fila = _filas(con, "select unidad_medida from resumen_indicadores where indicador = ?", [codigo])
    if not fila:
        raise ValueError(f"El indicador '{codigo}' no existe")
    return fila[0]["unidad_medida"]


def listar_indicadores():
    """Último valor y variaciones de todos los indicadores."""
    with conectar() as con:
        filas = _filas(con, """
            select indicador, nombre, unidad_medida, fecha_ultimo_valor,
                   ultimo_valor::double as ultimo_valor, tipo_variacion,
                   variacion_30d::double as variacion_30d, variacion_12m::double as variacion_12m
            from resumen_indicadores order by indicador
        """)
    return {"indicadores": [{k: (str(v) if isinstance(v, date) else v) for k, v in f.items()}
                            for f in filas]}


def obtener_serie(codigo, desde=None, hasta=None):
    """Resumen de la serie entre dos fechas: primero, último, mínimo, máximo y cantidad."""
    with conectar() as con:
        unidad = _unidad(con, codigo)
        datos = _filas(con, """
            select fecha, valor::double as valor from historico_indicadores
            where indicador = ?
              and fecha <= current_date
              and (?::date is null or fecha >= ?::date)
              and (?::date is null or fecha <= ?::date)
            order by fecha
        """, [codigo, desde, desde, hasta, hasta])
    if not datos:
        return {"indicador": codigo, "cantidad": 0, "mensaje": "No hay datos en ese rango de fechas"}
    minimo = min(datos, key=lambda d: d["valor"])
    maximo = max(datos, key=lambda d: d["valor"])
    return {
        "indicador": codigo,
        "unidad": unidad,
        "cantidad": len(datos),
        "primero": {"fecha": str(datos[0]["fecha"]), "valor": datos[0]["valor"]},
        "ultimo": {"fecha": str(datos[-1]["fecha"]), "valor": datos[-1]["valor"]},
        "minimo": {"fecha": str(minimo["fecha"]), "valor": minimo["valor"]},
        "maximo": {"fecha": str(maximo["fecha"]), "valor": maximo["valor"]},
    }


def calcular_variacion(codigo, desde, hasta=None):
    """Cambio entre dos fechas. En % para montos; en puntos para indicadores que ya son %."""
    serie = obtener_serie(codigo, desde, hasta)
    if serie["cantidad"] == 0:
        return serie
    inicial, final = serie["primero"]["valor"], serie["ultimo"]["valor"]
    if serie["unidad"] == "Porcentaje":
        cambio, tipo = round(final - inicial, 2), "puntos"
    else:
        cambio, tipo = round(100 * (final / inicial - 1), 2), "%"
    return {
        "indicador": codigo,
        "desde": serie["primero"],
        "hasta": serie["ultimo"],
        "variacion": cambio,
        "tipo_variacion": tipo,
    }


CODIGOS = ["dolar", "euro", "uf", "utm", "ipc", "libra_cobre", "tpm", "imacec", "tasa_desempleo"]

# Descripción de cada herramienta en JSON Schema: así el modelo sabe qué existe y qué pedir.
DECLARACIONES = [
    {
        "name": "listar_indicadores",
        "description": "Último valor publicado de los 9 indicadores, con variación a 30 días y 12 meses.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "obtener_serie",
        "description": "Resumen de la historia de un indicador entre dos fechas (datos desde 2021): "
                       "primer y último valor, mínimo, máximo y cantidad de datos.",
        "parameters": {
            "type": "object",
            "properties": {
                "codigo": {"type": "string", "enum": CODIGOS},
                "desde": {"type": "string", "description": "Fecha inicial AAAA-MM-DD (opcional)"},
                "hasta": {"type": "string", "description": "Fecha final AAAA-MM-DD (opcional)"},
            },
            "required": ["codigo"],
        },
    },
    {
        "name": "calcular_variacion",
        "description": "Cuánto cambió un indicador entre dos fechas. Devuelve % para montos "
                       "(dólar, UF...) y puntos para indicadores que ya son porcentaje (IPC, TPM...).",
        "parameters": {
            "type": "object",
            "properties": {
                "codigo": {"type": "string", "enum": CODIGOS},
                "desde": {"type": "string", "description": "Fecha inicial AAAA-MM-DD"},
                "hasta": {"type": "string", "description": "Fecha final AAAA-MM-DD (opcional, por defecto hoy)"},
            },
            "required": ["codigo", "desde"],
        },
    },
]

FUNCIONES = {
    "listar_indicadores": listar_indicadores,
    "obtener_serie": obtener_serie,
    "calcular_variacion": calcular_variacion,
}


def ejecutar(nombre, argumentos):
    """Ejecuta la herramienta pedida por el modelo. Los errores vuelven como texto, no rompen el agente."""
    try:
        return FUNCIONES[nombre](**argumentos)
    except Exception as error:
        return {"error": str(error)}
