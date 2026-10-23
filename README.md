# Chile Data Platform

**Plataforma abierta de indicadores económicos de Chile: se actualiza sola cada día desde la fuente oficial, valida cada dato con pruebas automáticas y lo entrega por una API pública.**

[![CI](https://github.com/niberdi01gold/chile-data-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/niberdi01gold/chile-data-platform/actions/workflows/ci.yml)
[![Actualizar datos](https://github.com/niberdi01gold/chile-data-platform/actions/workflows/actualizar.yml/badge.svg)](https://github.com/niberdi01gold/chile-data-platform/actions/workflows/actualizar.yml)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![dbt](https://img.shields.io/badge/dbt-1.12-FF694B?logo=dbt&logoColor=white)
![DuckDB](https://img.shields.io/badge/DuckDB-1.5-FFF000?logo=duckdb&logoColor=black)
![Dagster](https://img.shields.io/badge/Dagster-1.13-4F43DD)
![FastAPI](https://img.shields.io/badge/FastAPI-0.143-009688?logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)
![Agente IA](https://img.shields.io/badge/Agente_IA-evals_13%2F13-8E75B2?logo=googlegemini&logoColor=white)

### 🔗 API en vivo: **https://chile-data-platform.onrender.com/docs** · 🟢 [Página de estado](https://niberdi01gold.github.io/chile-data-platform/)

> Plan gratuito: si nadie la usó en los últimos 15 minutos, la primera consulta tarda ~1 minuto en despertar.

## Qué entrega

Nueve indicadores, con su último valor y su variación a 30 días y 12 meses:

| Diarios | Mensuales |
| --- | --- |
| Dólar observado · Euro · UF · Cobre (USD/lb) · TPM | UTM · IPC · IMACEC · Tasa de desempleo |

```bash
curl https://chile-data-platform.onrender.com/indicadores/dolar
curl "https://chile-data-platform.onrender.com/indicadores/uf/serie?desde=2026-01-01"
```

| Endpoint | Devuelve |
| --- | --- |
| `GET /salud` | Estado del servicio y fecha del dato más reciente |
| `GET /indicadores` | Último valor de los 9 indicadores con sus variaciones |
| `GET /indicadores/{codigo}` | Un indicador (`dolar`, `uf`, `ipc`, `libra_cobre`…) |
| `GET /indicadores/{codigo}/serie?desde=&hasta=` | Historia entre dos fechas (desde 2021) |

## Arquitectura

```mermaid
flowchart LR
    A[API Banco Central<br/>fuente oficial] --> B[(bronze<br/>JSON crudo)]
    M[mindicador.cl<br/>respaldo] --> B
    B --> C[dbt: staging<br/>limpieza y deduplicación]
    C --> D[dbt: intermediate<br/>unión de fuentes]
    D --> E[dbt: marts<br/>tablas gold]
    E --> F[(warehouse.duckdb)]
    F --> G[FastAPI en Docker<br/>Render]
    G --> H[Usuarios]
```

**Todo corre solo, sin un computador encendido:**

1. Cada día a las 09:50 (hora de Chile), GitHub Actions extrae los datos del Banco Central.
2. dbt construye las capas y ejecuta **27 pruebas de calidad**. **Si alguna falla, no se publica nada**: la API sigue entregando los datos del día anterior, nunca datos malos.
3. La base resultante se publica como *release* de GitHub.
4. La API (Docker en Render) descarga la base más reciente al arrancar.

En desarrollo, el mismo flujo se orquesta con **Dagster**:

![Linaje en Dagster](docs/dagster-lineage.png)

## Decisiones de diseño

- **Arquitectura medallion** (bronze → silver → gold): la respuesta cruda se guarda tal cual llegó, con la fecha de extracción en el nombre del archivo. Cualquier dato se puede reconstruir.
- **Fuente oficial con respaldo.** El Banco Central es la fuente principal y mindicador.cl el respaldo. Si un indicador falta en el Banco Central, se usa mindicador.cl **para ese indicador completo**: nunca se mezclan fuentes dentro de una misma serie, porque pueden diferir en fechas de publicación.
- **Una sola fuente de verdad para la configuración.** Los códigos de series viven en `transform/seeds/series_bcch.csv`, que leen el extractor y dbt. Las reglas de calidad (frecuencia, días máximos sin datos, rango válido) viven en `reglas_indicadores.csv`.
- **Variaciones correctas según el tipo de indicador.** Los montos (dólar, UF) se comparan en %; los indicadores que ya son porcentaje (IPC, TPM, desempleo) se comparan en **puntos**: una TPM que pasa de 4,75 % a 4,50 % baja 0,25 puntos, no 5 %.
- **El IMACEC se calcula, no se copia.** El Banco Central lo entrega como índice (2018 = 100); dbt calcula la variación anual comparando cada mes con el mismo mes del año anterior.
- **La CI no depende de APIs externas.** Las pruebas usan una muestra real guardada en `tests/fixtures`, así un servicio externo caído no rompe el build.
- **API segura por diseño:** base en solo lectura y consultas parametrizadas (sin inyección SQL). Imagen Docker liviana (74 MB): solo FastAPI, Uvicorn y DuckDB.
- **Secretos fuera del código:** credenciales en `.env` (local) y GitHub Secrets (nube).

## Agente de IA con evaluaciones

Un agente que responde en español preguntas sobre los indicadores **consultando los datos reales**, nunca de memoria:

```
$ python -m agente "¿Cuánto ha subido el dólar este año?"
  [herramienta] calcular_variacion {'codigo': 'dolar', 'desde': '2026-01-01'}

En lo que va de 2026, el dólar ha subido un 7,87 %:
* 2 de enero de 2026: $907,13
* 21 de octubre de 2026: $978,56
```

- **Herramientas (function calling):** el modelo decide qué función usar (`listar_indicadores`, `obtener_serie`, `calcular_variacion`); el código la ejecuta contra DuckDB y le devuelve el resultado. Las cifras salen de la base, no del modelo.
- **Independiente del proveedor:** las herramientas son Python puro; hoy corre con Gemini (nivel gratuito) y cambiar a otro modelo es una clase nueva.
- **Resiliente:** cadena de modelos de respaldo ante saturación (503/504) o límites (429), tiempo máximo por llamada y detección de cuota diaria agotada.
- **Evaluaciones (`python -m evals`):** 13 casos cuya respuesta correcta se **calcula desde la base de datos** (sin IA), así se mantienen vigentes cada día. Califica con reglas verificables: la cifra correcta (tolerancia 1 %), la herramienta correcta, y que **reconozca lo que no sabe** (bitcoin, dólar blue argentino) en vez de inventar. Puntaje mínimo: 80 %.

**Resultado actual: 13/13 (100 %)** con `gemini-3.5-flash-lite`, entre 1 y 10 segundos por respuesta → [ver detalle](evals/resultados.md).

Decisión medida, no supuesta: se partió con el modelo más grande, que respondía en ~40 s y fallaba por tiempo (504) en horas de alta demanda. Las evaluaciones mostraron que el modelo *lite* acierta los 13 casos 10 veces más rápido, así que quedó como principal y los grandes como respaldo.

## Calidad

- **27 pruebas de datos en dbt:** unicidad, nulos, valores aceptados, relaciones, rangos por indicador, frescura según el calendario de publicación y meses faltantes.
- **17 pruebas con pytest**: 9 de la API y 8 del agente (herramientas, calificador y el ciclo de herramientas con un modelo simulado), sin llamar a ninguna IA.
- **CI en cada push:** instala todo en un Linux limpio, corre pytest, dbt build, valida Dagster y construye la imagen Docker.

![Linaje en dbt](docs/linaje-dbt.jpg)

## Incidentes reales

Este proyecto documenta sus fallas como lo haría un equipo en producción:

- **[IPC sin datos](docs/incidentes/2026-10-16-ipc-sin-datos.md):** la prueba de frescura detectó que mindicador.cl dejó de publicar el IPC después de diciembre de 2025. Se **midió** la latencia de las fuentes desde los servidores de GitHub (mindicador.cl 7,15 s vs. Banco Central 0,37 s) y se migró a la API oficial del Banco Central. Resuelto.

## Cómo correrlo localmente

```bash
git clone https://github.com/niberdi01gold/chile-data-platform
cd chile-data-platform
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Credenciales gratuitas del Banco Central: https://si3.bcentral.cl/Siete/es/Siete/API
echo "BCCH_USER=tu_correo" >> .env
echo "BCCH_PASS=tu_clave" >> .env

python src/extraer_bcch.py --desde 2021         # 1. extraer (bronze)
cd transform && dbt build --profiles-dir . && cd ..   # 2. transformar y probar
uvicorn api.main:app --reload                   # 3. API en http://127.0.0.1:8000/docs

dagster dev -f orquestacion/definitions.py      # opcional: orquestador en http://127.0.0.1:3000

# Agente de IA (clave gratuita en https://aistudio.google.com/apikey → GEMINI_API_KEY en .env)
python -m agente "¿Cuál fue el valor más alto del dólar en 2025?"
python -m evals                                 # evaluaciones del agente
```

Con Docker:

```bash
docker build -t chile-api .
docker run --rm -p 8000:8000 -v "$PWD/data:/app/data" chile-api
```

## Estructura

```
src/            extractores (Banco Central y mindicador.cl) y buscador de series
transform/      proyecto dbt: seeds, staging, intermediate, marts y pruebas
orquestacion/   definición de Dagster (assets y calendario diario)
agente/         agente de IA: herramientas y ciclo de function calling
evals/          evaluaciones del agente (casos, calificador y resultados)
api/            API FastAPI
tests/          pruebas de la API y del agente, y muestras de datos para la CI
docs/           incidentes y diagramas
.github/        CI, actualización diaria y diagnóstico de red
```

## English summary

Open data platform for Chilean economic indicators (USD/CLP, EUR, UF, UTM, CPI, IMACEC, copper, monetary policy rate, unemployment). A daily GitHub Actions job extracts data from the **Central Bank of Chile's official API**, builds a bronze/silver/gold lakehouse with **dbt + DuckDB**, runs 27 data-quality tests (freshness, ranges, gaps, uniqueness) and only publishes the database if every test passes. A **FastAPI** service, containerized with **Docker** and deployed on Render, serves the data publicly. Includes an **AI agent** (Gemini function calling over DuckDB) with an evaluation suite whose ground truth is computed from the database — 13/13 correct, including refusing out-of-scope questions instead of hallucinating. Orchestrated locally with **Dagster**; CI runs pytest, dbt, Dagster validation and the Docker build on every push. Includes a real incident postmortem: a source silently stopped publishing CPI, the freshness test caught it, source latency was measured from CI runners, and the pipeline was migrated to the official API with the previous source kept as a fallback.

## Autor

**Nicolás Berrios** · Copiapó, Chile · [GitHub](https://github.com/niberdi01gold) · [LinkedIn](https://linkedin.com/in/nicolas-berrios-b9165a431)
