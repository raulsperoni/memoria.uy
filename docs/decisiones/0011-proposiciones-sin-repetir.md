# 0011 — Las proposiciones no se acumulan y Jev descarta las repetidas

*Fecha: 2026-11-24 · Estado: vigente · Commits: 03e14e4*

## Decisión

Cuando una historia se vuelve a procesar, se quedan las frases que tienen
votos o están en una jornada y el resto se reemplaza. El modelo recibe las que
quedan para no repetirlas. Antes de publicar una frase nueva, Jev compara si
plantea la misma discusión que otra de la historia, o que otra del mismo tema
de los últimos 14 días; si es así, se descarta.

## Por qué

Cada reproceso agregaba dos frases publicadas sin borrar las anteriores. En
el primer día una historia llegó a 28 frases, casi todas variantes de las
mismas dos. Votar dos veces lo mismo arruina el juego y las burbujas.

## Consecuencias

- `manage.py limpiar_proposiciones` descarta las duplicadas que ya había (sin
  `--aplicar` solo muestra qué haría). Nunca toca frases con votos o jornada.
- El umbral es `UMBRAL_MISMA_PROPOSICION` (0,5).
