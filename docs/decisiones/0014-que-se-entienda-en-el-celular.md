# 0014 — Que el sitio se entienda en el celular la primera vez

*Fecha: 2026-11-25 · Estado: vigente · Commits: ff6f56c*

## Decisión

Aceptamos que el sitio puede ser difícil de entender para quien llega por
primera vez, sobre todo en el celular, y hacemos seis cambios: una línea que
explica el sitio y se puede cerrar, un menú con dos entradas principales (lo
demás en «más», cada una con su explicación), una frase que dice qué pasó en
cada nota editada antes del diff, las burbujas con lo legible primero y el
mapa plegado, el juego con una pregunta a la vez y hechos verificados en el
contexto, letra más grande y menos «//» en los textos que explican, y una
página por tema.

## Por qué

Llegó una crítica de producto. La mitad de lo que proponía ya existía
(contexto en la tarjeta, voto desde la historia, tarjeta para compartir,
páginas de entidad, «lo que nos une» en burbujas). Lo que sí tenía razón:
la portada no dice qué es el sitio, cinco botones del mismo peso confunden,
los diffs no se explican solos, el mapa de burbujas abre con «PCA + k-means»,
la explicación va en 11px gris y no hay forma de seguir un tema. Se validó
con un antes y después en pantalla de celular antes de tocar el código.

No aceptamos el banner «sin algoritmos de recomendación» ni cambiar el estilo
de terminal: queda en títulos, botones y logo.

## Cómo

- `archivo/templates/archivo/_nav.html`: explicación con ✕ (se recuerda en
  `localStorage`, no sale mientras se juega) y menú nuevo.
- `Cambio.frase`: «Medio cambió el titular. Lo vimos N horas después de
  publicada». Dice cuándo lo vimos, no cuándo editó el medio: solo sabemos
  que fue entre dos capturas.
- `juego/views.py` (`_hechos_contexto`): hasta 3 hechos no ocultos con sus
  medios. La predicción aparece al elegir opinión (sin JS se ven las dos); se
  mantienen los dos toques de 0010.
- «¿De qué se trata?» viene abierto solo en la primera frase del día; en las
  otras empuja los botones fuera de la pantalla.
- `/tema/<categoria>/` lista las historias de cada categoría.

«Esta historia viene de» (historias anteriores parecidas por coseno de
centroides) quedó afuera. Con 139 historias reales no hubo umbral que separe:
sobre 0.75 aparecían pares sin relación (una operación ferroviaria con un curso
de inteligencia artificial) y entre 0.65 y 0.70 pares claros (la elección y el
procesamiento de Lorena Roqueta en el BPS). Un vínculo falso le quita crédito
al sitio, así que no se muestra hasta tener una señal mejor.
