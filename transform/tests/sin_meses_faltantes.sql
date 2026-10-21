-- Falla si a un indicador mensual le falta algún mes entre su primer y su último dato.
with rango as (
    select s.indicador,
           date_trunc('month', min(s.fecha))::date as desde,
           date_trunc('month', max(s.fecha))::date as hasta
    from {{ ref('int_indicadores') }} s
    join {{ ref('reglas_indicadores') }} r using (indicador)
    where r.frecuencia = 'mensual'
    group by s.indicador
),

esperados as (
    select indicador, unnest(generate_series(desde, hasta, interval 1 month))::date as mes
    from rango
)

select e.indicador, e.mes as mes_faltante
from esperados e
left join {{ ref('int_indicadores') }} s
    on s.indicador = e.indicador and date_trunc('month', s.fecha) = e.mes
where s.fecha is null
