# 0018 — El tick guarda sus corridas en la base, no en el cache

*Fecha: 2026-11-27 · Estado: vigente · Commits: aa31b2d*

## Decisión

La última corrida de cada tarea de `manage.py tick` se guarda en la tabla
`TareaCorrida`. Antes estaba en el cache. Ajusta [0007](0007-deploy-sin-celery.md).

## Por qué

El cache en la base tiene un máximo de 300 entradas. Al pasarlo, Django borra
el primer tercio de las claves en orden alfabético. Las páginas cacheadas y el
límite de pedidos lo llenan seguido, y las claves del tick quedaban en ese
tercio. Sin la clave, cada tarea parecía no haber corrido nunca.

El 27/11 el resumen para staff salió dos veces, a las 09:02 y a las 10:34. En
el mismo tick volvieron a correr las burbujas y la carga de medios.

## Qué se descartó

Subir `MAX_ENTRIES`. El problema pasaría menos seguido, pero el cache puede
borrar cualquier clave, y lo que decide si una tarea corre no puede depender
de eso.
