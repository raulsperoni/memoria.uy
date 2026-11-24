# 0003 — Segunda vuelta: un archivo automático y un juego diario

*Fecha: 2026-11-21 · Estado: vigente · Commits: d343b01, cf4dfbc, ac6d838*

## Decisión

memoria.uy pasa a ser dos cosas: un archivo que captura solo las noticias
uruguayas y las convierte en hechos con fuente, y un juego diario con frases
opinables sacadas de esas noticias. Se conserva el motor de burbujas (0002) y
las entidades.

## Por qué

- Nadie tiene que traer las noticias: el rastreo y los modelos de lenguaje ya
  son baratos.
- El modelo es resistencia.uy (LUC Comparada): fuente primaria, qué cambió, y
  una página por cosa.
- Un juego diario trae gente todos los días y junta votos sobre las mismas
  frases, que es lo que les faltaba a las burbujas.

## Consecuencias

- Propuesta completa en [PROPUESTA_2027.md](../PROPUESTA_2027.md) y plan en
  [PLAN_2027.md](../PLAN_2027.md).
- La ingesta manual, la extensión y los proxies se borraron (b420be5).
