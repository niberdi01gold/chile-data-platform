-- Capa silver: una fila por indicador y fecha, sin duplicados y con la fecha en hora de Chile.

with crudo as (
    select codigo, nombre, unidad_medida, serie, filename
    from read_json('../data/bronze/mindicador/*/*.json', filename = true)
),

filas as (
    select
        codigo        as indicador,
        nombre,
        unidad_medida,
        unnest(serie) as punto,
        strptime(regexp_extract(filename, '(\d{8}T\d{6}Z)', 1), '%Y%m%dT%H%M%SZ') as extraido_en
    from crudo
)

select
    indicador || '_' || cast(timezone('America/Santiago', timezone('UTC', punto.fecha)) as date) as id,
    indicador,
    nombre,
    unidad_medida,
    cast(timezone('America/Santiago', timezone('UTC', punto.fecha)) as date) as fecha,
    punto.valor as valor,
    extraido_en
from filas
qualify row_number() over (partition by indicador, fecha order by extraido_en desc) = 1