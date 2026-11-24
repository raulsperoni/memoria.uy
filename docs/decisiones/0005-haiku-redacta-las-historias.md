# 0005 — Claude Haiku 5.5 redacta las historias

*Fecha: 2026-11-22 · Estado: vigente · Commits: b056f9e*

## Decisión

El título, el resumen, los hechos y las frases de cada historia los escribe
Claude Haiku 5.5. Si falla, se prueba GPT-6-luna y después GPT-5-nano.

## Por qué

Se compararon 11 modelos con 4 historias reales. Haiku dio los hechos más
completos y precisos y las frases más claras, a ~US$0,0018 por historia. Otros
puntuaron bien en métricas automáticas pero cometieron errores (decir
«Congreso» por Parlamento) o tardaban un minuto.

## Consecuencias

- No se le pasa `temperature`: Haiku 5.5 rechaza valores que no sean el de
  fábrica.
