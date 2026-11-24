# 0007 — Tareas periódicas con un cron, sin Celery ni Redis

*Fecha: 2026-11-22 · Estado: vigente · Commits: 443d7e1, 354c84f*

## Decisión

En Railway corren dos servicios del mismo código: la web, que se duerme sin
tráfico, y un cron que cada 15 minutos ejecuta `manage.py tick`. `tick`
decide qué tareas tocan. El caché es una tabla en Postgres.

## Por qué

Las tareas corren unas pocas veces por hora. No justifican un worker y un
Redis prendidos todo el día.

## Consecuencias

- Con `REDIS_URL` definido vuelve el modo Celery.
- `manage.py tick --listar` muestra la última corrida de cada tarea.
