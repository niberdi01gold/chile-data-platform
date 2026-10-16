"""Pruebas de calidad sobre la capa silver.

Cada regla devuelve las filas que la incumplen: si no devuelve nada, la prueba pasa.
Uso:
    python src/calidad.py
"""

import logging
import sys

import duckdb

SILVER = "data/silver/indicadores.parquet"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
log = logging.getLogger("calidad")

# Reglas de negocio por indicador:
#   frecuencia, días máximos desde el último dato publicado y rango de valores razonable
REGLAS = """
SELECT * FROM (VALUES
    ('dolar',          'diaria',   7,   600,    1500),
    ('euro',           'diaria',   7,   700,    1700),
    ('uf',             'diaria',   7,   25000,  50000),
    ('libra_cobre',    'diaria',   7,   2,      8),
    ('tpm',            'diaria',   7,   0,      15),
    ('utm',            'mensual',  45,  45000,  90000),
    ('ipc',            'mensual',  75,  -3,     5),
    ('imacec',         'mensual',  100, -20,    30),
    ('tasa_desempleo', 'mensual',  100, 3,      15)
) AS r(indicador, frecuencia, max_dias_sin_datos, minimo, maximo)
"""

PRUEBAS = {
    "sin duplicados (indicador, fecha)": f"""
        SELECT indicador, fecha, count(*) AS veces
        FROM '{SILVER}' GROUP BY indicador, fecha HAVING count(*) > 1
    """,
    "sin valores nulos": f"""
        SELECT indicador, fecha FROM '{SILVER}' WHERE valor IS NULL OR fecha IS NULL
    """,
    "todos los indicadores tienen reglas": f"""
        SELECT DISTINCT s.indicador FROM '{SILVER}' s
        WHERE s.indicador NOT IN (SELECT indicador FROM reglas)
    """,
    "valores dentro de rango": f"""
        SELECT s.indicador, s.fecha, s.valor, r.minimo, r.maximo
        FROM '{SILVER}' s JOIN reglas r USING (indicador)
        WHERE s.valor NOT BETWEEN r.minimo AND r.maximo
    """,
    "datos al día (frescura)": f"""
        SELECT r.indicador, max(s.fecha) AS ultimo_dato,
               current_date - max(s.fecha) AS dias_sin_datos, r.max_dias_sin_datos
        FROM reglas r LEFT JOIN '{SILVER}' s USING (indicador)
        GROUP BY r.indicador, r.max_dias_sin_datos
        HAVING max(s.fecha) IS NULL OR current_date - max(s.fecha) > r.max_dias_sin_datos
    """,
    "sin meses faltantes (indicadores mensuales)": f"""
        WITH rango AS (
            SELECT s.indicador,
                   date_trunc('month', min(s.fecha))::DATE AS desde,
                   date_trunc('month', max(s.fecha))::DATE AS hasta
            FROM '{SILVER}' s JOIN reglas r USING (indicador)
            WHERE r.frecuencia = 'mensual'
            GROUP BY s.indicador
        ),
        esperados AS (
            SELECT indicador, unnest(generate_series(desde, hasta, INTERVAL 1 MONTH))::DATE AS mes
            FROM rango
        )
        SELECT e.indicador, e.mes AS mes_faltante
        FROM esperados e
        LEFT JOIN '{SILVER}' s ON s.indicador = e.indicador AND date_trunc('month', s.fecha) = e.mes
        WHERE s.fecha IS NULL
    """,
}


def main():
    con = duckdb.connect()
    con.execute(f"CREATE TABLE reglas AS {REGLAS}")
    fallidas = 0

    for nombre, sql in PRUEBAS.items():
        problemas = con.sql(sql)
        cantidad = len(problemas.fetchall())
        if cantidad == 0:
            log.info("OK     %s", nombre)
        else:
            fallidas += 1
            log.error("FALLA  %s (%d filas)", nombre, cantidad)
            print(problemas.limit(10))

    if fallidas:
        log.error("%d de %d pruebas fallaron", fallidas, len(PRUEBAS))
        sys.exit(1)
    log.info("Todas las pruebas pasaron (%d)", len(PRUEBAS))


if __name__ == "__main__":
    main()