# 0016 — Fichas de entidades con Wikidata, solo si hay confianza alta

*Fecha: 2026-11-26 · Estado: vigente · Commits: 9cd5761, cc0adf0, 4fafd6b, 03218d4*

## Decisión

La página de cada persona, organización o lugar muestra una ficha (foto con
atribución, cargo, partido, descripción, resumen de Wikipedia y links) sacada
de Wikidata. Solo se asocia un ítem cuando el candidato es uruguayo, se llama
igual y Jev, con los hechos donde aparece la entidad, dice que es la misma con
margen sobre el segundo candidato. Si hay duda no se muestra nada.

## Por qué

Una ficha equivocada (otro Mario Bergara, el futbolista) le quita crédito al
sitio más de lo que le da una ficha correcta. Un archivo de noticias uruguayas
tiene muchos homónimos y nombres a medias («Sánchez», «Orsi»).

## Cómo

- Candidatos: `wbsearchentities` y, de lo que vuelve, solo personas con
  ciudadanía Uruguay (P27) u organizaciones y lugares con país Uruguay (P17).
- Nombre: igual a la etiqueta o a un alias. En personas también si las
  palabras del nombre (≥ 2) están todas en la etiqueta. Nombres de una palabra
  solo valen si son alias exacto.
- Decisión: pregunta tipada `misma_entidad` con los últimos 6 hechos y la
  descripción, cargo y partido del candidato. Umbral 0,8 y ventaja de 0,2
  sobre el segundo (`UMBRAL_WIKIDATA`, `MARGEN_WIKIDATA`). Dos homónimos que
  encajan igual no se asocian.
- Datos en `archivo.FichaEntidad` (1:1 con `Entidad`): QID, confianza y los
  campos mostrados. La foto es la URL de Commons con autor y licencia, sin
  descargar ni rehospedar.
- Staff corrige con `enriquecer_entidades --fijar ID QID` o `--anular ID`
  (también editando `qid` y `fijada` de la ficha). Con `fijada` la tarea no
  busca de nuevo; con un QID puesto solo refresca sus datos, nunca lo cambia.
- Tarea `fichas` del tick, cada hora: 15 entidades por corrida y 100 por día,
  nuevas antes que refrescos, más hechos primero (mínimo 2). Las asociadas se
  refrescan a los 30 días, las que no tuvieron candidato se reintentan a los 90.
  Tres errores seguidos cortan la corrida y no se marca la entidad, así se
  reintenta en el próximo tick.
