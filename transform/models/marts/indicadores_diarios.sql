-- Capa gold: un valor por día calendario para los indicadores diarios.
-- Fines de semana y feriados repiten el último valor publicado (forward fill).

with silver as (
    select * from {{ ref('int_indicadores') }}
),

calendario as (
    select unnest(generate_series(min(fecha), current_date, interval 1 day))::date as fecha
    from silver
),

indicadores as (
    select indicador from {{ ref('reglas_indicadores') }} where frecuencia = 'diaria'
),

grilla as (
    select i.indicador, c.fecha, s.valor, s.valor is not null as publicado
    from indicadores i
    cross join calendario c
    left join silver s on s.indicador = i.indicador and s.fecha = c.fecha
),

relleno as (
    select
        indicador,
        fecha,
        last_value(valor ignore nulls) over (partition by indicador order by fecha) as valor,
        publicado
    from grilla
)

select indicador || '_' || fecha as id, indicador, fecha, valor, publicado
from relleno
where valor is not null
