# 0017 — Fichas: lectura sin maxlag y reintento a los 14 días

*Fecha: 2026-11-26 · Estado: vigente · Commits: ddcb0a9*

## Decisión

Las consultas a Wikidata ya no mandan `maxlag`. Las entidades que Jev no
asocia se reintentan a los 14 días, no a los 90. Ajusta [0016](0016-fichas-de-wikidata.md).

## Por qué

`maxlag` sirve para que los bots que editan esperen cuando las réplicas van
atrasadas. Para leer no hace falta, y con el servicio de consultas atrasado
más de 5 s Wikidata rechazaba todos los pedidos. Esos rechazos se veían como
«límite de pedidos».

En la primera corrida en producción, Yamandú Orsi quedó sin ficha aunque
Wikidata lo tiene (Q19946921). Con 90 días, un rechazo de Jev dejaba fuera a
una entidad central por tres meses. Con 14, los hechos nuevos le dan otra
oportunidad pronto.

El resultado de cada corrida separa `sin_candidato` (Wikidata no tiene a nadie
uruguayo con ese nombre) de `dudosa` (hay candidato pero Jev no llegó al umbral).
