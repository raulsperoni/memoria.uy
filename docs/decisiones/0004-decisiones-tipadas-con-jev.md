# 0004 — Las decisiones de sí o no las toma Jev

*Fecha: 2026-11-22 · Estado: vigente · Commits: ac6d838, 2b41a56, 5c7405f*

## Decisión

Cada pregunta de sí o no, o de puntaje, sobre un registro la responde Jev, un
modelo de decisiones tipadas: si una nota es de interés público, si dos notas
cubren el mismo hecho, si una fuente respalda un hecho, si una edición cambia
el sentido, qué tan divisiva y qué tan clara es una frase. Las respuestas se
guardan con su entrada y no se vuelven a pedir.

## Por qué

Responde en ~0,1 s, con probabilidades calibradas y a una fracción del costo
de un modelo de lenguaje. Es bueno decidiendo sobre un registro y flojo
combinando varios, así que agrupar notas se hace primero con embeddings: Jev
decide solo en la zona de duda (similitud entre 0,40 y 0,75).

## Consecuencias

- Las preguntas viven en `archivo/providers/decide.py`. Hay un reemplazo con
  un modelo de lenguaje barato si Jev no está.
- Pasa por la misma cuenta de OpenRouter que el resto.
