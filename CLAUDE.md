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
| `core` | Usuarios/perfiles, `Entidad`, motor matemático de clustering (`core/clustering/`), emails. El sistema viejo (`Noticia`/`Voto`, timeline en `/noticias/`, `/mapa/`, `/clusters/report/`) queda como legado hasta borrarlo |

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

### Cluster name caching
Los nombres de clusters generados por LLM se cachean para evitar cambios
frecuentes cuando el contenido (noticias/entidades) no cambia:
- Modelo `ClusterNameCache`: hash del contenido → nombre + descripción
- TTL de 7 días: después se regenera aunque el contenido sea igual
- Hash basado en: top noticia IDs + entity names (ordenados)
- Ver `get_or_create_cluster_name()` en [core/tasks.py](core/tasks.py)

### Reporte de Investigación (`/clusters/report/`)

Reporte narrativo completo enfocado en **consenso oculto** entre burbujas. Diseñado para investigadores.

**Arquitectura de análisis:**
- `core/clustering/consensus.py`: Análisis cross-cluster, métricas de polarización
- `core/clustering/bridges.py`: Identificación de votantes "puente"
- `core/clustering/evolution.py`: Estabilidad temporal y drift de opiniones

**Secciones del reporte:**

1. **Executive Summary**
   - % de consenso cross-cluster
   - Noticias consensuadas vs divisivas
   - Número de bridge-builders
   - Patrones por tipo de entidad

2. **Consenso Oculto**
   - Carousel interactivo de noticias con alto consenso
   - Visualización de acuerdo por burbuja
   - Top 10 noticias donde todas las burbujas coinciden

3. **Lo que nos Divide**
   - Lista de noticias polarizantes
   - Heatmap de desacuerdo entre burbujas
   - Timeline de polarización (últimos 6 meses)

4. **Los Puentes (Bridge-Builders)**
   - Network visualization (D3.js)
   - Top 25 votantes que conectan múltiples burbujas
   - Estadísticas: fuerza de conexión, votos, clusters conectados

5. **Evolución Temporal**
   - Sankey diagram mejorado
   - Índice de estabilidad entre runs
   - Métricas over time (polarización, consenso, silhouette)

6. **Análisis por Burbuja**
   - Consenso interno
   - Entidades vistas positiva/negativamente
   - Top noticias con mayor acuerdo

**APIs JSON:**
- `/api/clustering/consensus/` - Datos de consenso y división
- `/api/clustering/bridges/` - Red de bridge-builders
- `/api/clustering/polarization-timeline/` - Métricas temporales
- `/api/clustering/stability/` - Índice de estabilidad

**Caching:**
- Executive summary: 1 hora
- Bridge analysis: 6 horas
- Evolution metrics: 24 horas

Ver `ClusterReportView` en [core/views_clustering.py](core/views_clustering.py).
Templates en [core/templates/clustering/report.html](core/templates/clustering/report.html).

### Analytics page (`/clusters/stats/`) - DEPRECATED

Mantenido por compatibilidad. Use `/clusters/report/` para el reporte completo.

Ver análisis técnico de evolución en [docs/CLUSTER_EVOLUTION_ANALYSIS.md](docs/CLUSTER_EVOLUTION_ANALYSIS.md).

### Viralización y compartir
Sistema de captura del mapa de burbujas para compartir en redes sociales:

1. **Botón "Compartir mi burbuja"** en `/mapa/`
   - Captura SVG real del mapa → convierte a JPEG optimizado (~50-80KB)
   - Sube imagen al servidor automáticamente (`/api/mapa/upload-og-image/`)
   - Mobile: Web Share API nativo (WhatsApp, etc.)
   - Desktop: Descarga imagen + copia texto

2. **Imágenes OG para links compartidos**
   - Endpoint: `/api/mapa/og-image/?cluster=X`
   - Sirve SOLO imágenes reales capturadas por usuarios (`media/og-images/og-cluster-X.jpg`)
   - Sin fallback generado - si no hay captura, muestra logo estático
   - Ventaja: Imagen OG es siempre el mapa REAL

3. **Flujo completo:**
   ```
   Usuario hace click "Compartir"
   → Captura SVG del mapa en el navegador
   → Convierte a JPEG con Canvas API
   → Sube al servidor (fire-and-forget)
   → Guarda como og-cluster-{id}.jpg
   → Próximo que comparta ese link verá la imagen real
   ```

Ver `svgToBlob()` y `uploadOGImage()` en [visualization.html](core/templates/clustering/visualization.html)
y `upload_cluster_og_image()` en [core/views_clustering.py](core/views_clustering.py).

## Testing

- pytest con pytest-django
- Fixtures en `conftest.py`
- Tests en `core/tests/`, `archivo/tests/`, `juego/tests/`
- Tests corren sin Redis (cache en tabla de la base; `conftest.py` la crea)

## Deployment

### Railway (setup barato)
Dos servicios del mismo repo + Postgres, sin Redis:
- **web** (`railway.toml`): migra, crea la tabla de cache y levanta gunicorn; duerme sin tráfico.
- **cron** (`railway.cron.toml`): `manage.py tick` cada 15 min.

Con `REDIS_URL` definido vuelve a funcionar el modo Celery (worker/beat) del `Dockerfile`.

### Docker
```bash
docker-compose up -d --build
```

## Archivos clave

| Archivo | Propósito |
|---------|-----------|
| `core/views.py` | Timeline viejo (legado), perfil |
| `core/feeds.py` | Algoritmos de feeds: recientes, confort (afín), puente (testeables, sin request) |
| `core/views_clustering.py` | Mapa de burbujas, reporte de investigación, APIs de análisis |
| `core/templates/clustering/report.html` | Reporte narrativo completo |
| `core/templates/clustering/components/` | Componentes modulares del reporte |
| `core/clustering/consensus.py` | Análisis de consenso cross-cluster |
| `core/clustering/bridges.py` | Identificación de bridge-builders |
| `core/clustering/evolution.py` | Métricas de estabilidad temporal |
| `core/clustering/pca.py` | PCA sparsity-aware |
| `core/clustering/kmeans.py` | K-Means clustering |
| `core/clustering/hierarchical.py` | Agrupación jerárquica |
| `core/clustering/metrics.py` | Métricas de calidad |
| `core/tasks.py` | Celery tasks |
| `core/parse.py` | Nombres de burbujas con LLM |
| `core/forms.py` | CustomSignupForm con alias |
| `core/signals.py` | Vote claiming, UserProfile auto-create |
| `archivo/pipeline.py` | Pipeline de ingesta (testeable, sin Celery) |
| `archivo/llm.py` | Prompt y esquema de historias |
| `archivo/providers/` | Cloudflare, Jev, embeddings, R2 |
| `juego/logica.py` | Armado de jornada, puntaje, racha |
| `juego/burbujas.py` | Burbujas sobre proposiciones |
