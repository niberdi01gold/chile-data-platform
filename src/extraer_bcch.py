"""Extrae indicadores desde la API oficial del Banco Central de Chile (capa bronze).

Uso:
    python src/extraer_bcch.py                 # carga diaria: últimos ~2 años
    python src/extraer_bcch.py --desde 2018    # carga histórica

Credenciales en .env (nunca en el código): BCCH_USER y BCCH_PASS
La lista de series vive en transform/seeds/series_bcch.csv (la misma que usa dbt).
"""

import argparse
import csv
import json
import logging
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from extraer import crear_sesion  # noqa: E402  (reutiliza la sesión con reintentos)

RAIZ = Path(__file__).resolve().parent.parent
URL = "https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx"
SERIES_CSV = RAIZ / "transform" / "seeds" / "series_bcch.csv"
CARPETA_BRONZE = RAIZ / "data" / "bronze" / "bcch"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
log = logging.getLogger("extraer_bcch")


def leer_series():
    """Devuelve {indicador: código del Banco Central} desde el CSV compartido con dbt."""
    with open(SERIES_CSV, encoding="utf-8") as f:
        return {fila["indicador"]: fila["codigo_bcch"] for fila in csv.DictReader(f)}


def credenciales():
    load_dotenv(RAIZ / ".env")
    usuario, clave = os.getenv("BCCH_USER"), os.getenv("BCCH_PASS")
    if not usuario or not clave:
        raise SystemExit("Faltan BCCH_USER y BCCH_PASS (archivo .env o variables de entorno)")
    return {"user": usuario, "pass": clave}


def extraer(sesion, cred, codigo, desde, hasta):
    """Pide una serie al Banco Central y valida la respuesta."""
    respuesta = sesion.get(URL, params={
        **cred, "function": "GetSeries", "timeseries": codigo,
        "firstdate": str(desde), "lastdate": str(hasta),
    }, timeout=60)
    respuesta.raise_for_status()
    datos = respuesta.json()
    if datos.get("Codigo") != 0:
        raise ValueError(f"El Banco Central respondió: {datos.get('Descripcion')}")
    if not isinstance(datos.get("Series", {}).get("Obs"), list):
        raise ValueError("Respuesta sin observaciones")
    return datos


def guardar(indicador, datos, etiqueta):
    """Guarda la respuesta tal cual llegó (bronze). El nombre indica qué se pidió y cuándo."""
    ahora = datetime.now(timezone.utc)
    carpeta = CARPETA_BRONZE / indicador
    carpeta.mkdir(parents=True, exist_ok=True)
    archivo = carpeta / f"{etiqueta}_{ahora:%Y%m%dT%H%M%SZ}.json"
    archivo.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    return archivo


def ejecutar(desde=None):
    """Extrae todas las series. Devuelve (registros por indicador, lista de fallidos)."""
    hasta = date.today() + timedelta(days=40)       # la UF se publica por adelantado
    inicio = date(desde, 1, 1) if desde else date.today() - timedelta(days=800)
    etiqueta = str(desde) if desde else "ultimos"
    sesion, cred = crear_sesion(), credenciales()
    registros, fallidos = {}, []

    for indicador, codigo in leer_series().items():
        try:
            datos = extraer(sesion, cred, codigo, inicio, hasta)
            archivo = guardar(indicador, datos, etiqueta)
            registros[indicador] = len(datos["Series"]["Obs"])
            log.info("%-16s %5d registros -> %s", indicador, registros[indicador], archivo.name)
        except Exception as error:                  # un indicador que falla no detiene a los demás
            log.error("%-16s FALLÓ: %s", indicador, error)
            fallidos.append(indicador)
    return registros, fallidos


def main():
    parser = argparse.ArgumentParser(description="Extractor del Banco Central de Chile")
    parser.add_argument("--desde", type=int, help="año inicial para una carga histórica")
    registros, fallidos = ejecutar(parser.parse_args().desde)
    if fallidos:
        log.error("Terminó con %d fallas: %s", len(fallidos), ", ".join(fallidos))
        sys.exit(1)
    log.info("Terminó sin errores")


if __name__ == "__main__":
    main()
