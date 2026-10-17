-- Capa gold: último valor de cada indicador y su variación a 30 días y 12 meses.

with silver as (
    select * from {{ ref('stg_indicadores') }}
),

ultimo as (
    select indicador, nombre, unidad_medida, fecha, valor
    from silver
    where fecha <= current_date          -- la UF y la UTM vienen publicadas por adelantado
    qualify row_number() over (partition by indicador order by fecha desc) = 1
)

select
    u.indicador,
    u.nombre,
    u.unidad_medida,
    u.fecha as fecha_ultimo_valor,
    u.valor as ultimo_valor,
    case when u.unidad_medida = 'Porcentaje' then 'puntos' else '%' end as tipo_variacion,
    case when u.unidad_medida = 'Porcentaje'
         then round(u.valor - m30.valor, 2)
         else round(100 * (u.valor / m30.valor - 1), 2)
    end as variacion_30d,
    case when u.unidad_medida = 'Porcentaje'
         then round(u.valor - m365.valor, 2)
         else round(100 * (u.valor / m365.valor - 1), 2)
    end as variacion_12m
from ultimo u
asof left join silver m30
    on m30.indicador = u.indicador and m30.fecha <= u.fecha - interval 30 day
asof left join silver m365
    on m365.indicador = u.indicador and m365.fecha <= u.fecha - interval 365 day
