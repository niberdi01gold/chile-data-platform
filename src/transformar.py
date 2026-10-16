"""Fase 2: de bronze (JSON crudo) a silver (tabla limpia en Parquet), usando DuckDB.

Uso:
    python src/transformar.py
"""

import logging
from pathlib import Path

import duckdb

BRONZE = "data/bronze/mindicador/*/*.json"
SILVER = Path("data/silver/indicadores.parquet")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
log = logging.getLogger("transformar")

SQL_SILVER = f"""
WITH crudo AS (
    -- 1. Leer todos los JSON de bronze; filename = de qué archivo vino cada fila
    SELECT codigo, nombre, unidad_medida, serie, filename
    FROM read_json('{BRONZE}', filename = true)
),
filas AS (
    -- 2. "Desarmar" la lista serie: una fila por cada fecha
    SELECT
        codigo                                        AS indicador,
        nombre,
        unidad_medida,
        unnest(serie)                                 AS punto,
        -- la fecha de extracción viene en el nombre del archivo: ..._20261016T224843Z.json
        strptime(regexp_extract(filename, '(\\d{{8}}T\\d{{6}}Z)', 1), '%Y%m%dT%H%M%SZ') AS extraido_en
    FROM crudo
)
SELECT
    indicador,
    nombre,
    unidad_medida,
    -- 3. La API da la medianoche de Chile expresada en UTC (03:00 o 04:00 según el horario).
    --    Se convierte a hora de Chile antes de quedarse con la fecha.
    CAST(timezone('America/Santiago', timezone('UTC', punto.fecha)) AS DATE) AS fecha,
    punto.valor                                       AS valor,
    extraido_en
FROM filas
-- 4. Una misma fecha puede venir en varios archivos (carga histórica + cargas diarias).
--    Nos quedamos con la extracción más reciente.
QUALIFY row_number() OVER (PARTITION BY indicador, fecha ORDER BY extraido_en DESC) = 1
ORDER BY indicador, fecha
"""


def main():
    con = duckdb.connect()
    SILVER.parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"COPY ({SQL_SILVER}) TO '{SILVER.as_posix()}' (FORMAT parquet)")

    resumen = con.sql(f"""
        SELECT indicador, count(*) AS registros, min(fecha) AS desde, max(fecha) AS hasta
        FROM '{SILVER.as_posix()}'
        GROUP BY indicador ORDER BY indicador
    """)
    log.info("Silver escrito en %s", SILVER)
    print(resumen)


if __name__ == "__main__":
    main()