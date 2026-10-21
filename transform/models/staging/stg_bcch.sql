-- Capa silver (Banco Central): una fila por indicador y fecha, sin duplicados.
-- El IMACEC llega como índice (2018=100); aquí se convierte a variación anual (%),
-- que es como se publica y compara normalmente.

with crudo as (
    select
        regexp_extract(filename, '[\\/]bcch[\\/]([a-z_]+)[\\/]', 1) as indicador,
        unnest(Series.Obs) as obs,
        strptime(regexp_extract(filename, '(\d{8}T\d{6}Z)', 1), '%Y%m%dT%H%M%SZ') as extraido_en
    from {{ source('bcch', 'bronze') }}
),

observaciones as (
    select
        indicador,
        -- DuckDB puede leer la fecha como texto (DD-MM-AAAA) o ya como fecha (AAAA-MM-DD)
        coalesce(
            try_strptime(obs.indexDateString::varchar, '%d-%m-%Y'),
            try_strptime(obs.indexDateString::varchar, '%Y-%m-%d')
        )::date as fecha,
        try_cast(obs.value as double) as valor,
        extraido_en
    from crudo
    where obs.statusCode = 'OK'                     -- descarta días sin dato ("ND" / "NaN")
    qualify row_number() over (partition by indicador, fecha order by extraido_en desc) = 1
),

imacec_variacion as (
    -- Variación anual: cada mes contra el mismo mes del año anterior
    select
        actual.indicador,
        actual.fecha,
        round(100 * (actual.valor / anterior.valor - 1), 1) as valor,
        actual.extraido_en
    from observaciones actual
    join observaciones anterior
        on anterior.indicador = actual.indicador
       and anterior.fecha = actual.fecha - interval 1 year
    where actual.indicador = 'imacec'
),

unido as (
    select * from observaciones where indicador <> 'imacec'
    union all
    select * from imacec_variacion
)

select
    u.indicador || '_' || u.fecha as id,
    u.indicador,
    s.nombre,
    s.unidad_medida,
    u.fecha,
    u.valor,
    u.extraido_en
from unido u
join {{ ref('series_bcch') }} s using (indicador)
where u.valor is not null
