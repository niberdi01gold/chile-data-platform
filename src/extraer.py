"""Fase 1: extrae indicadores de mindicador.cl y guarda la respuesta cruda (capa bronze)."""

import json
from datetime import datetime, timezone
from pathlib import Path

import requests

URL_BASE = "https://mindicador.cl/api"
INDICADORES = ["dolar", "euro", "uf", "utm", "ipc", "libra_cobre", "tpm", "imacec", "tasa_desempleo"]
CARPETA_BRONZE = Path("data/bronze/mindicador")


def extraer(indicador):
    """Pide un indicador a la API y devuelve la respuesta como diccionario de Python."""
    respuesta = requests.get(f"{URL_BASE}/{indicador}", timeout=30)
    respuesta.raise_for_status()
    return respuesta.json()


def guardar(indicador, datos):
    """Guarda la respuesta tal cual llegó, en un archivo con la fecha y hora de extracción."""
    ahora = datetime.now(timezone.utc)
    carpeta = CARPETA_BRONZE / indicador
    carpeta.mkdir(parents=True, exist_ok=True)
    archivo = carpeta / f"{ahora:%Y%m%dT%H%M%SZ}.json"
    archivo.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    return archivo


if __name__ == "__main__":
    for indicador in INDICADORES:
        datos = extraer(indicador)
        archivo = guardar(indicador, datos)
        print(f"{indicador:15} {len(datos['serie']):3} registros -> {archivo}")