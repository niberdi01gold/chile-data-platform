"""Orquestación del pipeline con Dagster.

Une las dos partes del proyecto en un solo flujo:
    extracción (Python)  ->  modelos y pruebas de dbt

Uso (desde la carpeta raíz del proyecto):
    dagster dev -f orquestacion/definitions.py
"""

import sys
from pathlib import Path

import dagster as dg
from dagster_dbt import DbtCliResource, DbtProject, dbt_assets

RAIZ = Path(__file__).resolve().parent.parent

# Para poder reutilizar las funciones de src/extraer.py
sys.path.insert(0, str(RAIZ / "src"))
import extraer  # noqa: E402
import extraer_bcch  # noqa: E402

extraer.CARPETA_BRONZE = RAIZ / "data" / "bronze" / "mindicador"   # ruta absoluta, sin depender de la carpeta actual


# ---------------------------------------------------------------- 1. Extracción
@dg.asset(
    key=["mindicador", "bronze"],         # el mismo nombre que la fuente de dbt: así Dagster las conecta
    group_name="ingesta",
    description="Descarga los últimos valores de cada indicador desde mindicador.cl (capa bronze).",
)
def bronze_mindicador(context: dg.AssetExecutionContext) -> dg.MaterializeResult:
    sesion = extraer.crear_sesion()
    registros, fallidos = {}, []

    for indicador in extraer.INDICADORES:
        try:
            datos = extraer.extraer(sesion, indicador)
            extraer.guardar(indicador, datos)
            registros[indicador] = len(datos["serie"])
            context.log.info(f"{indicador}: {registros[indicador]} registros")
        except Exception as error:        # un indicador que falla no detiene a los demás
            context.log.error(f"{indicador} FALLÓ: {error}")
            fallidos.append(indicador)

    if not registros:
        raise Exception("Fallaron todos los indicadores: la API no responde")
    if fallidos:
        context.log.warning(f"Indicadores con falla: {', '.join(fallidos)}")

    return dg.MaterializeResult(
        metadata={
            "indicadores_ok": len(registros),
            "indicadores_fallidos": dg.MetadataValue.text(", ".join(fallidos) or "ninguno"),
            "registros": dg.MetadataValue.json(registros),
        }
    )


@dg.asset(
    key=["bcch", "bronze"],               # el mismo nombre que la fuente "bcch" de dbt
    group_name="ingesta",
    description="Descarga las series oficiales del Banco Central de Chile (fuente principal, capa bronze).",
)
def bronze_bcch(context: dg.AssetExecutionContext) -> dg.MaterializeResult:
    registros, fallidos = extraer_bcch.ejecutar()
    if not registros:
        raise Exception("Fallaron todas las series del Banco Central")
    if fallidos:
        context.log.warning(f"Series con falla: {', '.join(fallidos)} (se usará mindicador.cl de respaldo)")
    return dg.MaterializeResult(
        metadata={
            "series_ok": len(registros),
            "series_fallidas": dg.MetadataValue.text(", ".join(fallidos) or "ninguna"),
            "registros": dg.MetadataValue.json(registros),
        }
    )


# ---------------------------------------------------------------- 2. dbt
proyecto_dbt = DbtProject(project_dir=RAIZ / "transform", profiles_dir=RAIZ / "transform")
proyecto_dbt.prepare_if_dev()             # con "dagster dev", vuelve a leer el proyecto dbt en cada inicio


@dbt_assets(manifest=proyecto_dbt.manifest_path)
def modelos_dbt(context: dg.AssetExecutionContext, dbt: DbtCliResource):
    # "dbt build" = seeds + modelos + pruebas, en el orden correcto
    yield from dbt.cli(["build"], context=context).stream()


# ---------------------------------------------------------------- 3. Calendario
pipeline_diario = dg.define_asset_job(
    name="pipeline_diario",
    selection=dg.AssetSelection.all(),
    description="Extrae los indicadores y reconstruye silver y gold con sus pruebas.",
)

todos_los_dias = dg.ScheduleDefinition(
    job=pipeline_diario,
    cron_schedule="0 10 * * *",           # todos los días a las 10:00
    execution_timezone="America/Santiago",
)


defs = dg.Definitions(
    assets=[bronze_mindicador, bronze_bcch, modelos_dbt],
    jobs=[pipeline_diario],
    schedules=[todos_los_dias],
    resources={"dbt": DbtCliResource(project_dir=proyecto_dbt)},
)
