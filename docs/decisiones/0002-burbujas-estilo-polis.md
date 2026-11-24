# 0002 — Burbujas de votantes al estilo Polis

*Fecha: 2026-01-04 · Estado: vigente (el motor se reutiliza en 0003) · Commits: 0b2abe9, 0075975*

## Decisión

Los votantes se agrupan por cómo votan, al estilo de Polis: reducción de
dimensiones que tolera matrices con muchos huecos y grupos elegidos por
silhouette (`core/clustering/`). Cada grupo tiene una descripción.

## Por qué

Mostrar en qué coincide la gente y en qué se separa es más útil que un
promedio. Polis ya probó que funciona en debates públicos.

## Consecuencias

- Con ~333 votantes, casi todos anónimos, y noticias que duran un día, la
  matriz quedó muy dispersa. «Mirá tu burbuja» fue curiosidad de una vez.
- Los algoritmos están en [SCIENTIFIC.md](../SCIENTIFIC.md).
