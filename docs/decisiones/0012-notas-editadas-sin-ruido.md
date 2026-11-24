# 0012 — Una nota editada es un cambio en el texto, no en la captura

*Fecha: 2026-11-24 · Estado: vigente · Commits: f0592b5*

## Decisión

Al volver a capturar una nota no se registra un cambio si la captura nueva es
mucho más corta que la anterior o se corta en una palabra con «…» (muro de
pago), si la anterior era la recortada, o si lo único que cambia son
titulares de otras notas del mismo medio. La nota conserva el texto completo.

## Por qué

En el primer día, 22 de las 26 ediciones de cuerpo registradas eran falsas.
la diaria muestra a veces la nota completa y a veces el comienzo con «…»
detrás del muro de pago. Subrayado mete en la nota un bloque de últimas
noticias, y cada vez que entraba una nota nueva todas las anteriores
parecían editadas. Jev les daba 0,7 a 0,9 de «cambia el sentido», así que
eran las más visibles.

## Consecuencias

- Las 4 que quedan son ediciones reales; por ejemplo, Telemundo sacó una
  frase sobre el vínculo de una candidata con el Partido Nacional.
- `manage.py revisar_cambios` aplica las reglas a las ya registradas (sin
  `--aplicar` solo muestra qué haría).
- Un recorte a menos del 60 % que sea una edición real no se registra. Es
  raro y se puede ajustar con `RATIO_RECORTE`.
