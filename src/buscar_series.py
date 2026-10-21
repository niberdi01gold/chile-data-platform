"""Busca series en el catálogo del Banco Central.

Uso:
    python src/buscar_series.py MONTHLY "precios al consumidor" variación
    (todas las palabras deben aparecer en el título)
"""

import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()
URL = "https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx"

frecuencia, palabras = sys.argv[1], [p.lower() for p in sys.argv[2:]]
catalogo = requests.get(URL, params={
    "user": os.getenv("BCCH_USER"), "pass": os.getenv("BCCH_PASS"),
    "function": "SearchSeries", "frequency": frecuencia,
}, timeout=60).json()["SeriesInfos"]

encontradas = [s for s in catalogo if all(p in s["spanishTitle"].lower() for p in palabras)]
print(f"{len(encontradas)} series (se muestran 15)\n")
for s in encontradas[:15]:
    print(f"{s['seriesId']:<38} {s['spanishTitle'][:110]}")
    