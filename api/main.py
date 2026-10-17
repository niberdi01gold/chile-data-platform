"""API pública de indicadores económicos de Chile.

Lee las tablas gold que construye dbt (data/warehouse.duckdb) y las expone como JSON.

Uso (desde la carpeta raíz del proyecto):
    uvicorn api.main:app --reload
Documentación interactiva: http://127.0.0.1:8000/docs
"""

import os
from datetime import date
from pathlib import Path

import duckdb
from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel

RAIZ = Path(__file__).resolve().parent.parent
RUTA_BD = os.getenv("RUTA_BD", str(RAIZ / "data" / "warehouse.duckdb"))

app = FastAPI(
    title="Chile Data Platform API",
    description="Indicadores económicos de Chile (dólar, UF, UTM, IPC, cobre...) actualizados a diario.",
    version="1.0.0",
)


# ---------------------------------------------------------------- Conexión
def obtener_bd():
    """Abre la base en modo solo lectura en cada petición y la cierra al terminar.

    Solo lectura: la API nunca modifica datos, y así no bloquea a dbt cuando escribe.
    """
    con = duckdb.connect(RUTA_BD, read_only=True)
    try:
        yield con
    finally:
        con.close()


def a_diccionarios(resultado):
    """Convierte el resultado de DuckDB en una lista de diccionarios (lo que FastAPI convierte a JSON)."""
    columnas = [c[0] for c in resultado.description]
    return [dict(zip(columnas, fila)) for fila in resultado.fetchall()]


# ---------------------------------------------------------------- Modelos de respuesta
# Describen la forma exacta del JSON. FastAPI los usa para validar y para la documentación.
class Resumen(BaseModel):
    indicador: str
    nombre: str
    unidad_medida: str
    fecha_ultimo_valor: date
    ultimo_valor: float
    tipo_variacion: str
    variacion_30d: float | None
    variacion_12m: float | None


class Punto(BaseModel):
    fecha: date
    valor: float


class Serie(BaseModel):
    indicador: str
    desde: date | None
    hasta: date | None
    cantidad: int
    datos: list[Punto]


class Salud(BaseModel):
    estado: str
    indicadores: int
    ultimo_dato: date | None


# ---------------------------------------------------------------- Endpoints
@app.get("/", include_in_schema=False)
def inicio():
    return {"mensaje": "Chile Data Platform API", "documentacion": "/docs"}


@app.get("/salud", response_model=Salud, tags=["Sistema"])
def salud(bd=Depends(obtener_bd)):
    """Comprueba que la API puede leer la base y muestra la fecha del dato más reciente."""
    indicadores, ultimo = bd.execute(
        "select count(*), max(fecha_ultimo_valor) from resumen_indicadores"
    ).fetchone()
    return {"estado": "ok", "indicadores": indicadores, "ultimo_dato": ultimo}


@app.get("/indicadores", response_model=list[Resumen], tags=["Indicadores"])
def listar_indicadores(bd=Depends(obtener_bd)):
    """Último valor de todos los indicadores, con su variación a 30 días y 12 meses."""
    return a_diccionarios(bd.execute("select * from resumen_indicadores order by indicador"))


@app.get("/indicadores/{codigo}", response_model=Resumen, tags=["Indicadores"])
def obtener_indicador(codigo: str, bd=Depends(obtener_bd)):
    """Último valor de un indicador. Ejemplos de código: dolar, uf, utm, ipc, libra_cobre."""
    filas = a_diccionarios(
        bd.execute("select * from resumen_indicadores where indicador = ?", [codigo.lower()])
    )
    if not filas:
        raise HTTPException(status_code=404, detail=f"Indicador '{codigo}' no existe")
    return filas[0]


@app.get("/indicadores/{codigo}/serie", response_model=Serie, tags=["Indicadores"])
def obtener_serie(
    codigo: str,
    desde: date | None = Query(None, description="Fecha inicial (AAAA-MM-DD)"),
    hasta: date | None = Query(None, description="Fecha final (AAAA-MM-DD)"),
    bd=Depends(obtener_bd),
):
    """Historia de un indicador entre dos fechas (por defecto, toda la serie)."""
    codigo = codigo.lower()
    existe = bd.execute(
        "select count(*) from resumen_indicadores where indicador = ?", [codigo]
    ).fetchone()[0]
    if not existe:
        raise HTTPException(status_code=404, detail=f"Indicador '{codigo}' no existe")
    if desde and hasta and desde > hasta:
        raise HTTPException(status_code=400, detail="'desde' no puede ser posterior a 'hasta'")

    # Los "?" son parámetros: DuckDB inserta los valores de forma segura (evita inyección SQL)
    datos = a_diccionarios(bd.execute(
        """
        select fecha, valor
        from historico_indicadores
        where indicador = ?
          and (? is null or fecha >= ?)
          and (? is null or fecha <= ?)
        order by fecha
        """,
        [codigo, desde, desde, hasta, hasta],
    ))
    return {"indicador": codigo, "desde": desde, "hasta": hasta, "cantidad": len(datos), "datos": datos}
