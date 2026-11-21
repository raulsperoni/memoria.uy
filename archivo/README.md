# archivo

Captura automática de noticias uruguayas → historias con hechos (con
procedencia) y proposiciones. Ver [docs/PLAN_2027.md](../docs/PLAN_2027.md).

## Puesta en marcha

```bash
poetry run python manage.py migrate
poetry run python manage.py cargar_medios      # medios iniciales (§16 del plan)
poetry run python manage.py detectar_feeds     # busca RSS/sitemaps (requiere red abierta)
```

Revisar en `/admin/archivo/medio/` los que quedaron sin feeds y cargarlos a mano.

Celery beat corre solo (ver `memoria/celery.py`):

| Task | Frecuencia |
|---|---|
| `archivo.tasks.ciclo_ingesta` | cada 30 min |
| `archivo.tasks.procesar_historias` | cada 15 min |
| `archivo.tasks.recrawls_pendientes` | cada hora (:40) |
| `archivo.tasks.cerrar_historias` | cada hora (:05) |

## Variables de entorno

| Variable | Default | Para qué |
|---|---|---|
| `INGESTA_ACTIVA` | `True` | Kill-switch de toda la ingesta |
| `EXTRACTOR` | `trafilatura` | `cloudflare` en producción |
| `CLOUDFLARE_ACCOUNT_ID` | — | Cuenta Cloudflare |
| `CLOUDFLARE_API_TOKEN` | — | Token con Browser Rendering (Edit) + Workers AI (Read) |
| `EMBEDDER` | `workers_ai` | `workers_ai` / `litellm` |
| `DECIDER` | `jev` | `jev` / `llm` |
| `TYPESAFE_API_KEY` | — | Key de Jev (o la de OpenRouter si se usa `TYPESAFE_BASE_URL`) |
| `TYPESAFE_BASE_URL` | `https://api.typesafe.ai` | `https://openrouter.ai/api` para ir por OpenRouter |
| `TYPESAFE_DEFAULT_MODEL` | `jev-latest` | `typesafe/jev-router` vía OpenRouter |
| `OPENROUTER_API_KEY` | — | LLM de historias (ya existente) |
| `ARCHIVO_LLM_MODELS` | flash-lite | Modelos en orden de fallback, separados por coma |
| `SNAPSHOT_STORAGE` | `local` | `r2` en producción |
| `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` / `R2_BUCKET` | — / — / `memoria-snapshots` | Credenciales R2 |
| `MAX_EXTRACCIONES_DIA` | `150` | Cupo diario de extracciones |
| `RECRAWL_OFFSETS_HORAS` | `24,168` | Cuándo re-capturar notas top |
| `UMBRAL_INTERES` | `0.5` | Filtro 1 (antes de extraer) |
| `UMBRAL_VALE_HISTORIA` | `0.34` | Filtro 2 (historias de un solo medio) |
| `UMBRAL_FIEL` / `UMBRAL_CALIDAD` | `0.5` / `0.6` | Verificación de hechos / proposiciones |
| `SIM_MISMA_HISTORIA` / `SIM_DUDA_HISTORIA` | `0.75` / `0.55` | Agrupamiento por embeddings (bge-m3) |

## Páginas

`/archivo/` hoy · `/archivo/AAAA/M/D/` día · `/h/<slug>/` historia ·
`/e/<id>/<slug>/` entidad · `/cambios/` notas editadas · `/medios/<slug>/` ·
`/buscar/?q=`

## Tests

```bash
poetry run pytest archivo
```

Todos los proveedores tienen versión `Fake` (ver `archivo/tests/test_pipeline.py`).
