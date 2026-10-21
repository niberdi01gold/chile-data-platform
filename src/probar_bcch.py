"""Prueba la API del Banco Central y busca los códigos de las series que necesitamos.

Uso:
    python src/probar_bcch.py
Requiere en .env: BCCH_TOKEN, o bien BCCH_USER y BCCH_PASS
"""

import os
from datetime import date, timedelta

import requests
from dotenv import load_dotenv

load_dotenv()
URL = "https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx"

if os.getenv("BCCH_TOKEN"):
    CREDENCIALES = {"token": os.getenv("BCCH_TOKEN")}
    print("Usando: token")
elif os.getenv("BCCH_USER") and os.getenv("BCCH_PASS"):
    CREDENCIALES = {"user": os.getenv("BCCH_USER"), "pass": os.getenv("BCCH_PASS")}
    print("Usando: usuario y contraseña")
else:
    raise SystemExit("Faltan credenciales en el archivo .env")

# 1) ¿Funcionan las credenciales? Pedimos el dólar observado de los últimos 10 días
hoy = date.today()
r = requests.get(URL, params={
    **CREDENCIALES, "function": "GetSeries", "timeseries": "F073.TCO.PRE.Z.D",
    "firstdate": str(hoy - timedelta(days=10)), "lastdate": str(hoy),
}, timeout=30).json()
print("Prueba de credenciales:", r["Codigo"], r["Descripcion"])
if r["Codigo"] != 0:
    raise SystemExit("Las credenciales no funcionan.")
for obs in r["Series"]["Obs"][-3:]:
    print("   dólar", obs["indexDateString"], obs["value"])

# 2) Buscar los códigos de las demás series en el catálogo
BUSCAR = {
    "DAILY": ["unidad de fomento", "euro", "cobre"],
    "MONTHLY": ["unidad tributaria", "consumidor", "desocupación", "imacec"],
}
print("\nSeries candidatas:")
for frecuencia, palabras in BUSCAR.items():
    catalogo = requests.get(URL, params={
        **CREDENCIALES, "function": "SearchSeries", "frequency": frecuencia,
    }, timeout=60).json()["SeriesInfos"]
    for palabra in palabras:
        encontradas = [s for s in catalogo if palabra in s["spanishTitle"].lower()]
        print(f"\n[{frecuencia}] '{palabra}': {len(encontradas)} series (se muestran 6)")
        for s in encontradas[:6]:
            print(f"   {s['seriesId']:<40} {s['spanishTitle'][:90]}")
            