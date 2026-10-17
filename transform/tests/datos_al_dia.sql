-- Falla si un indicador lleva más días sin datos de lo que permite su calendario de publicación.
-- severity = warn: avisa sin detener el pipeline. Hay un incidente abierto conocido
-- (docs/incidentes/2026-10-16-ipc-sin-datos.md) y no debe bloquear al resto de los indicadores.
{{ config(severity = 'warn') }}

select r.indicador, max(s.fecha) as ultimo_dato,
       current_date - max(s.fecha) as dias_sin_datos, r.max_dias_sin_datos
from {{ ref('reglas_indicadores') }} r
left join {{ ref('stg_indicadores') }} s using (indicador)
group by r.indicador, r.max_dias_sin_datos
having max(s.fecha) is null or current_date - max(s.fecha) > r.max_dias_sin_datos
