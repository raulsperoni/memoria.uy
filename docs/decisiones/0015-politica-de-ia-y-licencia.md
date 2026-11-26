# 0015 — Política de IA y licencia: nos pueden leer y citar, con CC BY 4.0

*Fecha: 2026-11-26 · Estado: vigente · Commits: ebbde5f, fecf81b*

## Decisión

Los crawlers y agentes de IA pueden leer, indexar y citar todo lo público de
memoria.uy, y `robots.txt` lo dice con un grupo por cada bot conocido. Se
bloquea solo lo que no debe indexarse: la búsqueda, el voto, los resultados
personales, el admin y las cuentas. Lo que produce memoria.uy (hechos,
proposiciones, resúmenes, datos agregados y CSV) tiene licencia CC BY 4.0. El
texto de los medios no se relicencia ni se republica: en `.md`, `.json`, feeds
y CSV van hechos, resúmenes propios, títulos, enlaces a la nota original y la
cita breve que respalda cada hecho, nunca el cuerpo de las notas.

## Por qué

El objetivo del sitio es ser fuente primaria de «qué pasó, con fuentes». Un
modelo o un buscador que cite bien a memoria.uy cumple ese objetivo; uno que
no pueda leerlo, no. La auditoría SEO/AX del 26/11/2026 encontró que el sitio
dejaba entrar a todos pero no lo decía, no tenía `llms.txt`, feed ni formato
para máquinas, y «usalos libremente citando» no es una licencia que una
empresa o un modelo pueda aplicar.

Se eligió CC BY 4.0 y no CC0 porque pedimos atribución con enlace a la
historia, que es lo que hace que la cita lleve de vuelta a las fuentes. Se
separó lo propio de lo ajeno porque los títulos y las citas son de los medios:
los publicamos como evidencia de procedencia, no los licenciamos.

El juego sigue siendo para personas. No hay API de voto con token y `llms.txt`
pide no automatizarlo: un voto de agente contamina las burbujas. Los agentes
tienen solo lectura.

## Cómo

- `memoria/views.py`: `robots_txt` (grupo `*` y un grupo para los bots de IA,
  con las mismas reglas; `Content-Signal` es un estándar nuevo, los parsers que
  no lo conocen lo ignoran) y `llms_txt` (`core/templates/llms.txt`).
- `/h/<slug>.md`, `/h/<slug>.json`, `/feed.xml`, `/cambios/feed.xml`,
  `/datos/fuentes.csv` y `/datos/hechos.jsonl`; cada hecho tiene ancla
  `#hecho-<id>`. `archivo/formatos.py`, `archivo/feeds.py`.
- JSON-LD en `archivo/estructurados.py` (`NewsArticle` con cada hecho como
  `Claim`, `Person`/`Organization`/`Place`, `Dataset`, `WebSite`,
  `BreadcrumbList`), con `license`. No hay `ClaimReview`: Google exige una
  calificación y «las fuentes difieren» no se puede traducir a una sin
  inventarla.
- Licencia dicha en «Acerca de», en privacidad, en `/datos/`, en `llms.txt`,
  en el pie, en cada CSV (columna `licencia`) y en `LICENCIA-DATOS.md`.
- La búsqueda lleva `noindex,follow` y además está en `robots.txt`: es
  redundante a propósito para los agentes que ignoran uno de los dos.
