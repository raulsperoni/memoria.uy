# CLAUDE.md

Guía técnica para Claude Code cuando trabaja con este repositorio.

Ver también:
- [VISION.md](VISION.md) - Visión de producto y estado actual
- [docs/SCIENTIFIC.md](docs/SCIENTIFIC.md) - Algoritmos y referencias científicas

## Comandos de desarrollo

```bash
# Servidor local
poetry run python manage.py runserver

# Migraciones
poetry run python manage.py makemigrations
poetry run python manage.py migrate

# Tests
poetry run pytest
poetry run pytest --cov=. --cov-report=html
poetry run pytest -k "test_vote"

# Tareas periódicas (sin Celery/Redis)
poetry run python manage.py tick --listar
poetry run python manage.py tick

# Archivo y juego
poetry run python manage.py cargar_medios
poetry run python manage.py detectar_feeds
poetry run python manage.py probar_archivo URL [URL ...]
poetry run python manage.py armar_jornada

# Tailwind
poetry run python manage.py tailwind start
```

## Arquitectura (desde nov 2026)

Ver [docs/PROPUESTA_2027.md](docs/PROPUESTA_2027.md) (por qué) y
[docs/PLAN_2027.md](docs/PLAN_2027.md) (cómo). Tres apps:

| App | Qué hace |
|-----|----------|
| `archivo` | Ingesta automática de medios → Historias con Hechos (con procedencia) y Proposiciones; snapshots y detección de notas editadas. Ver [archivo/README.md](archivo/README.md) |
| `juego` | Juego diario «¿Qué piensa Uruguay?» (5 proposiciones, voto + predicción) y burbujas de opinión sobre proposiciones |
| `core` | `Entidad`, motor de clustering (`core/clustering/`, lo usa `juego/burbujas.py`), `tick`, resumen diario para staff, páginas acerca/privacidad, 404/429/500. El producto anterior (votar noticias, `/noticias/`, `/mapa/`, `/clusters/*`) se borró en nov 2026; sus URLs redirigen (301) a `/` o `/burbujas/` |

### Flujo de datos

1. **Descubrir** (RSS/sitemaps, gratis) → `Fuente`
2. **Filtrar**: secciones + decisión tipada (Jev) «¿interés público uruguayo?»
3. **Extraer**: Cloudflare Browser Rendering + trafilatura → `Snapshot` privado (R2)
4. **Agrupar**: embeddings (Workers AI bge-m3) → `Historia`
5. **Procesar**: LLM (Claude Haiku 5.5 vía OpenRouter) → `Hecho` + `Proposicion` + `Entidad`
6. **Verificar**: Jev chequea cada hecho contra cada fuente, el resumen y la calidad de proposiciones
7. **Recrawl** de historias top a 24 h / 7 días → `Cambio` (diff, ¿cambia el sentido?)
8. **Jornada** diaria 05:30 → juego; **burbujas** diarias 02:15 (todo vía `manage.py tick`)

### Proveedores intercambiables (`archivo/providers/`)

Extractor, Decider (decisiones tipadas sí/no/score con caché en `Decision`),
Embedder y Storage; cada uno con versión `Fake` para tests. Selección por env
(ver `archivo/README.md`).

### Sesiones

Votante = usuario autenticado, o id anónimo guardado en los **datos** de la
sesión (`juego/votante.py`; no se usa `session_key` porque Django la rota al
hacer login). Al iniciar sesión los votos anónimos pasan a la cuenta
(`juego/signals.py`).

### URL normalization

Ver `normalize_url()` en [core/utils.py](core/utils.py): quita parámetros de
tracking y fragmentos antes de guardar URLs.

## Patrones importantes

### Task locking
Todos los Celery tasks usan `@task_lock(timeout=...)` para prevenir ejecución
duplicada.

### Model fallback en LLM
`archivo/llm.py` y `core/parse.py` prueban modelos en orden. No pasar
`temperature`: Claude Haiku 5.5 rechaza valores no default.

### Clustering Polis-style
Motor matemático en `core/clustering/`, reutilizado por `juego/burbujas.py`
sobre proposiciones. Ver [docs/SCIENTIFIC.md](docs/SCIENTIFIC.md).

## Testing

- pytest con pytest-django
- Fixtures en `conftest.py`
- Tests en `core/tests/`, `archivo/tests/`, `juego/tests/`
- Tests corren sin Redis (cache en tabla de la base; `conftest.py` la crea)

## Deployment

### Railway (setup barato)
Proyecto `memoria-uy`: dos servicios del mismo repo (Dockerfile) + Postgres, sin Redis.
La configuración vive en Railway (config-as-code está deprecado allá):
- **web**: start `/entrypoint.sh web` (migra, crea tabla de cache, gunicorn), healthcheck `/health/`, sleep sin tráfico. Necesita `PORT=8000`: el dominio público de Railway enruta al 8000 y sin la variable gunicorn escucha en el 8080 que inyecta Railway.
- **cron**: start `/entrypoint.sh tick`, cron `*/15 * * * *`, restart NEVER.

Con `REDIS_URL` definido vuelve a funcionar el modo Celery (worker/beat) del `Dockerfile`.

Dominio: `memoria.uy` en Cloudflare (cuenta propia), CNAME a Railway sin proxy. Los snapshots van al bucket R2 `memoria-snapshots` de la misma cuenta; las credenciales R2 salen del mismo token de Cloudflare.

### Docker
```bash
docker-compose up -d --build
```

## Archivos clave

| Archivo | Propósito |
|---------|-----------|
| `archivo/pipeline.py` | Pipeline de ingesta (testeable, sin Celery) |
| `archivo/llm.py` | Prompt y esquema de historias |
| `archivo/providers/` | Cloudflare, Jev, embeddings, R2 |
| `juego/logica.py` | Armado de jornada, puntaje, racha |
| `juego/burbujas.py` | Burbujas sobre proposiciones |
| `juego/votante.py` | Identidad del votante (anónimo o usuario) |
| `core/clustering/` | PCA sparsity-aware, grupos por silhouette |
| `core/parse.py` | Nombres de burbujas con LLM |
| `core/management/commands/tick.py` | Tareas periódicas (cron de Railway) |
| `core/tasks.py` | `task_lock` y resumen diario para staff |
