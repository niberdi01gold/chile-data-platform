-- Une las dos fuentes. Regla: si el Banco Central (fuente oficial) tiene datos de un
-- indicador, se usa SOLO el Banco Central para ese indicador. mindicador.cl queda como
-- respaldo para los indicadores que el Banco Central no entregue.
-- (No se mezclan fuentes dentro de un mismo indicador: pueden diferir en fechas de publicación.)

with bcch as (
    select *, 'bcch' as fuente from {{ ref('stg_bcch') }}
),

mindicador as (
    select *, 'mindicador' as fuente from {{ ref('stg_indicadores') }}
    where indicador not in (select distinct indicador from bcch)
)

select * from bcch
union all
select * from mindicador
