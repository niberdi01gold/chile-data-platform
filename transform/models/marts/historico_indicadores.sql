-- Capa gold: la serie completa de cada indicador, tal como se publicó (sin rellenar días).
-- Es la tabla que usa la API para el endpoint /serie.

select
    id,
    indicador,
    fecha,
    valor
from {{ ref('stg_indicadores') }}
