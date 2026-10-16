"""Extrae indicadores económicos de mindicador.cl y guarda la respuesta cruda (capa bronze).

Uso:
    python src/extraer.py                    # carga diaria: últimos valores de cada indicador
    python src/extraer.py --desde 2020       # carga histórica: un archivo por indicador y año
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

URL_BASE = "https://mindicador.cl/api"
INDICADORES = ["dolar", "euro", "uf", "utm", "ipc", "libra_cobre", "tpm", "imacec", "tasa_desempleo"]
CARPETA_BRONZE = Path("data/bronze/mindicador")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
log = logging.getLogger("extraer")


def crear_sesion():
    """Sesión HTTP que reintenta sola si la API falla momentáneamente."""
    reintentos = Retry(
        total=3,                                   # hasta 3 reintentos
        backoff_factor=2,                          # espera 2, 4 y 8 segundos entre intentos
        status_forcelist=[429, 500, 502, 503, 504],  # errores que vale la pena reintentar
    )
    sesion = requests.Session()
    sesion.mount("https://", HTTPAdapter(max_retries=reintentos))
    return sesion


def extraer(sesion, indicador, anio=None):
    """Pide un indicador (los últimos valores, o un año completo) y valida la respuesta."""
    url = f"{URL_BASE}/{indicador}" + (f"/{anio}" if anio else "")
    respuesta = sesion.get(url, timeout=30)
    respuesta.raise_for_status()
    datos = respuesta.json()

    # Validación mínima: que la respuesta tenga la forma que esperamos
    if not isinstance(datos.get("serie"), list):
        raise ValueError(f"Respuesta sin 'serie' para {indicador}: {list(datos)}")
    return datos


def guardar(indicador, datos, anio=None):
    """Guarda la respuesta tal cual llegó. El nombre indica qué se pidió y cuándo."""
    ahora = datetime.now(timezone.utc)
    carpeta = CARPETA_BRONZE / indicador
    carpeta.mkdir(parents=True, exist_ok=True)
    archivo = carpeta / f"{anio or 'ultimos'}_{ahora:%Y%m%dT%H%M%SZ}.json"
    archivo.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    return archivo


def main():
    parser = argparse.ArgumentParser(description="Extractor de indicadores de mindicador.cl")
    parser.add_argument("--desde", type=int, help="año inicial para una carga histórica")
    args = parser.parse_args()

    anios = range(args.desde, datetime.now().year + 1) if args.desde else [None]
    sesion = crear_sesion()
    fallidos = []

    for indicador in INDICADORES:
        for anio in anios:
            nombre = f"{indicador} {anio or ''}".strip()
            try:
                datos = extraer(sesion, indicador, anio)
                archivo = guardar(indicador, datos, anio)
                log.info("%-22s %4d registros -> %s", nombre, len(datos["serie"]), archivo)
            except Exception as error:   # un indicador que falla no detiene a los demás
                log.error("%-22s FALLÓ: %s", nombre, error)
                fallidos.append(nombre)

    if fallidos:
        log.error("Terminó con %d fallas: %s", len(fallidos), ", ".join(fallidos))
        sys.exit(1)                       # código de salida 1 = algo falló (el orquestador lo detecta)
    log.info("Terminó sin errores")


if __name__ == "__main__":
    main()