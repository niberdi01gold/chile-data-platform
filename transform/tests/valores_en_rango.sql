-- Falla si algún valor está fuera del rango razonable definido para su indicador.
select s.indicador, s.fecha, s.valor, r.minimo, r.maximo
from {{ ref('int_indicadores') }} s
join {{ ref('reglas_indicadores') }} r using (indicador)
where s.valor not between r.minimo and r.maximo
