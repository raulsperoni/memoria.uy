# 0006 — Cada hecho se verifica contra cada nota

*Fecha: 2026-11-22 · Estado: vigente · Commits: f7ccfaa*

## Decisión

Después de redactar una historia, cada hecho se chequea contra cada nota de la
historia. Un medio aparece al lado de un hecho solo si su nota lo respalda, y
un hecho sin ninguna nota que lo respalde se borra. El resumen se chequea
contra los hechos; si dice algo que no está, se rearma con los hechos.

## Por qué

El archivo vale por la procedencia. Un modelo de lenguaje puede atribuir un
dato al medio equivocado o agregar uno que ninguna nota dice.

## Consecuencias

- Detecta datos inventados, pero se le escapan errores sutiles, como un número
  mal contado. Lo dice la página «Acerca de».
