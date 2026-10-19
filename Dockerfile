# Imagen de la API: Python + FastAPI + DuckDB, nada más.
FROM python:3.12-slim

WORKDIR /app

# 1) Primero solo las dependencias: Docker guarda esta capa en caché y no
#    reinstala todo cada vez que cambias el código.
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2) Después el código
COPY api/ api/

# La base de datos no va dentro de la imagen: se conecta desde afuera (volumen)
ENV RUTA_BD=/app/data/warehouse.duckdb

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
