# 0013 — El tono de los medios mide cómo queda parada la persona

*Fecha: 2026-11-24 · Estado: vigente · Commits: 740e5ef*

## Decisión

Para cada nota y cada persona de su historia que la nota nombra, Haiku dice
cómo la deja parada, de −2 (muy mal) a +2 (muy bien), con una cita textual y
una razón. Se mide la valencia de la nota, no el encuadre del medio: una
imputación o una crítica fuerte cuenta como negativa aunque la nota esté
contada con neutralidad. Es una llamada aparte por nota, solo para personas, y
Jev verifica que la cita respalde la valencia; si la cita no está en la nota o
Jev no la respalda, el tono se descarta. La página de cada persona muestra el
promedio por medio, con las notas y sus citas.

## Por qué

La primera versión tenía sentimiento por noticia y entidad, pero nunca se
llenó y se borró con el producto anterior (0009). La página de una persona es
la que más interés despierta, y la pregunta natural es cómo la tratan los
medios. La valencia es más fácil de medir con consistencia y de explicar que
el encuadre. La contra es que no separa al medio de la noticia: un medio que
cubre más las malas noticias de alguien sale más negativo aunque no tenga
sesgo. La página lo dice y muestra la cantidad de notas.

Una llamada por nota, en vez de agregarlo al JSON de la historia, cuesta más
pero cada nota se juzga sola, sin que el modelo compare medios ni se contagie
de las otras notas.

## Cómo

- `archivo/tonos.py` (`LLMTonador` / `FakeTonador`), modelo `archivo.Tono`.
- Tarea `tonos` del tick cada 30 min, notas nuevas primero, con cupo de 500
  llamadas por día (`MAX_TONOS_DIA`) y a lo sumo 30 notas o 10 minutos por
  corrida, al final del tick. La misma cola vacía las notas viejas;
  `manage.py tonos_backfill` empuja a mano o cuenta lo pendiente.
- Una historia reprocesada vuelve a la cola, pero solo se calculan las
  personas que falten.
- Próximo: filtrar en el juego notas que dejan bien o mal a alguien y usar
  los tonos en las burbujas.
