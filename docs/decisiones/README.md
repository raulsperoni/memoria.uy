# Decisiones

Registro fechado de las decisiones que el código no explica solo. Solo se
agrega, nunca se reescribe.

- Un archivo por decisión: `NNNN-titulo-corto.md`, numerados en orden.
- **Nunca se reescribe una.** Si una decisión se revierte, se agrega otra que
  lo dice y enlaza a la que reemplaza.
- Vale un registro todo lo que haría preguntar «¿por qué está así?» cuando la
  respuesta no está en el diff.
- Cada registro abre con el título y una línea con `Fecha`, `Estado` y
  `Commits` (los commits donde se implementó). La página «Acerca de» arma la
  línea de tiempo con esa línea y el primer párrafo de «Decisión».

| # | Decisión |
|---|----------|
| [0001](0001-votar-noticias.md) | Primera versión: votar las noticias que trae la gente |
| [0002](0002-burbujas-estilo-polis.md) | Burbujas de votantes al estilo Polis |
| [0003](0003-segunda-vuelta.md) | Segunda vuelta: un archivo automático y un juego diario |
| [0004](0004-decisiones-tipadas-con-jev.md) | Las decisiones de sí o no las toma Jev |
| [0005](0005-haiku-redacta-las-historias.md) | Claude Haiku 5.5 redacta las historias |
| [0006](0006-cada-hecho-contra-cada-nota.md) | Cada hecho se verifica contra cada nota |
| [0007](0007-deploy-sin-celery.md) | Tareas periódicas con un cron, sin Celery ni Redis |
| [0008](0008-datos-abiertos.md) | Datos abiertos, nunca votos individuales |
| [0009](0009-borrar-el-producto-anterior.md) | Se borra el producto anterior |
| [0010](0010-dos-toques-por-frase.md) | Juego: dos toques por frase, y «no sé» pasa |
| [0011](0011-proposiciones-sin-repetir.md) | Las proposiciones no se acumulan y Jev descarta las repetidas |
| [0012](0012-notas-editadas-sin-ruido.md) | Una nota editada es un cambio en el texto, no en la captura |
| [0013](0013-tono-de-los-medios.md) | El tono de los medios mide cómo queda parada la persona |
| [0014](0014-que-se-entienda-en-el-celular.md) | Que el sitio se entienda en el celular la primera vez |
| [0015](0015-politica-de-ia-y-licencia.md) | Política de IA y licencia: nos pueden leer y citar, con CC BY 4.0 |
| [0016](0016-fichas-de-wikidata.md) | Fichas de entidades con Wikidata, solo si hay confianza alta |

El registro de la noche del 21 al 22/11/2026
([DECISIONES_2026-11-22.md](../DECISIONES_2026-11-22.md)) queda como estaba;
sus decisiones están acá en 0003–0008.
