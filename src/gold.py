"""Capa gold: tablas listas para la API, el dashboard y los análisis.

Uso:
    python src/gold.py
"""

import logging
from pathlib import Path

import duckdb

SILVER = "data/silver/indicadores.parquet"
GOLD = Path("data/gold")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
log = logging.getLogger("gold")

# 1. Último valor de cada indicador y cómo ha cambiado
SQL_RESUMEN = f"""
WITH ordenado AS (
    SELECT *,
           row_number() OVER (PARTITION BY indicador ORDER BY fecha DESC) AS n
    FROM '{SILVER}'
    WHERE fecha <= current_date          -- la UF y la UTM vienen publicadas por adelantado
),
ultimo AS (
    SELECT indicador, nombre, unidad_medida, fecha, valor FROM ordenado WHERE n = 1
)
SELECT
    u.indicador,
    u.nombre,
    u.unidad_medida,
    u.fecha                       AS fecha_ultimo_valor,
    u.valor                       AS ultimo_valor,
    -- valor más reciente de hace al menos 30 y 365 días (ASOF JOIN busca "el último antes de")
    round(100 * (u.valor / m30.valor - 1), 2)  AS variacion_30d_pct,
    round(100 * (u.valor / m365.valor - 1), 2) AS variacion_12m_pct
FROM ultimo u
ASOF LEFT JOIN '{SILVER}' m30
    ON m30.indicador = u.indicador AND m30.fecha <= u.fecha - INTERVAL 30 DAY
ASOF LEFT JOIN '{SILVER}' m365
    ON m365.indicador = u.indicador AND m365.fecha <= u.fecha - INTERVAL 365 DAY
ORDER BY u.indicador
"""

# 2. Un valor por día calendario para los indicadores diarios.
#    Fines de semana y feriados repiten el último valor publicado (forward fill).
SQL_DIARIO = f"""
WITH calendario AS (
    SELECT unnest(generate_series(min(fecha), current_date, INTERVAL 1 DAY))::DATE AS fecha
    FROM '{SILVER}'
),
indicadores AS (
    SELECT DISTINCT indicador FROM '{SILVER}'
    WHERE indicador IN ('dolar', 'euro', 'uf', 'libra_cobre', 'tpm')
),
grilla AS (
    SELECT i.indicador, c.fecha, s.valor, s.valor IS NOT NULL AS publicado
    FROM indicadores i
    CROSS JOIN calendario c
    LEFT JOIN '{SILVER}' s ON s.indicador = i.indicador AND s.fecha = c.fecha
)
SELECT indicador, fecha, valor_relleno AS valor, publicado
FROM (
    SELECT
        indicador,
        fecha,
        last_value(valor IGNORE NULLS) OVER (PARTITION BY indicador ORDER BY fecha) AS valor_relleno,
        publicado                -- false = valor repetido de un día anterior
    FROM grilla
)
WHERE valor_relleno IS NOT NULL  -- descarta los días previos al primer dato
ORDER BY indicador, fecha
"""


def main():
    GOLD.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()

    for nombre, sql in [("resumen_indicadores", SQL_RESUMEN), ("indicadores_diarios", SQL_DIARIO)]:
        destino = (GOLD / f"{nombre}.parquet").as_posix()
        con.execute(f"COPY ({sql}) TO '{destino}' (FORMAT parquet)")
        filas = con.sql(f"SELECT count(*) FROM '{destino}'").fetchone()[0]
        log.info("%-22s %6d filas -> %s", nombre, filas, destino)

    print(con.sql(f"SELECT * EXCLUDE (nombre) FROM '{(GOLD / 'resumen_indicadores.parquet').as_posix()}'"))


if __name__ == "__main__":
    main()