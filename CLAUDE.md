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

# Celery (requiere Redis)
poetry run celery -A memoria worker --loglevel=info

# Clustering manual
poetry run python manage.py cluster_voters --days 30 --min-voters 50

# Tailwind
poetry run python manage.py tailwind start
```

## Arquitectura

### Flujo de datos

1. **Submission**: Usuario envía URL via web o extensión
2. **Captura**: Extensión captura HTML completo (bypasea paywalls)
3. **Enrichment**: Celery task extrae título, resumen, entidades via LLM
4. **Voting**: Usuario vota (buena/mala/neutral)
5. **Clustering**: Task periódico agrupa votantes por patrones

### Modelos principales

- `Noticia`: URL, metadata, HTML capturado
- `Voto`: Opinión de usuario sobre noticia (usuario o session_key)
- `Entidad`: Personas, organizaciones, lugares extraídos
- `VoterCluster*`: Modelos de clustering (Run, Cluster, Projection, etc.)
- `ClusterNameCache`: Cache de nombres LLM con TTL de 7 días
- `UserProfile`: Alias, preferencias de email, show_alias_on_map

### Sesiones

Prioridad de identificación de votante:
1. Usuario autenticado → `usuario` field
2. Extensión → header `X-Extension-Session` o cookie `memoria_extension_session`
3. Django session → `session_key`

Ver `get_voter_identifier()` en [core/views.py](core/views.py).

### URL normalization

URLs are automatically normalized before storage to prevent duplicates:
- Strips tracking parameters (utm_*, fbclid, gclid, etc.)
- Removes URL fragments (# anchors)
- Preserves functional parameters (search queries, IDs, etc.)
- Ensures same article from different sources deduplicates

Ver `normalize_url()` en [core/utils.py](core/utils.py).

## Patrones importantes

### Signup prompt
Aparece después del 3er voto o al agotar noticias disponibles ("estado vacío").
- Lógica en `VoteView.post()` y `NewsTimelineView.get_context_data()`
- Banner flotante: `signup_prompt.html`
- Form custom: `CustomSignupForm` (extiende allauth)
- Al crear cuenta: signal auto-crea `UserProfile`

### Vote claiming
Al hacer login/signup, los votos anónimos se vinculan a la cuenta:
- Signal `reclaim_session_votes` en [core/signals.py](core/signals.py)
- Detecta session_key de extensión o Django
- Transfiere votos a usuario
- Previene duplicados (prioridad a voto de usuario)

### Task locking
Todos los Celery tasks usan `@task_lock(timeout=...)` para prevenir ejecución
duplicada.

### Model fallback en AI parsing
Si el modelo primario falla, automáticamente intenta el siguiente en prioridad.
Ver [core/parse.py](core/parse.py).

### Clustering Polis-style
Motor matemático en `core/clustering/`. Ver [docs/SCIENTIFIC.md](docs/SCIENTIFIC.md)
para detalles de algoritmos.

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
- Tests en `core/tests/`

## Deployment

### Railway
Tres servicios: web, worker, beat. Todos comparten `REDIS_URL`.

### Docker
```bash
docker-compose up -d --build
```

## Archivos clave

| Archivo | Propósito |
|---------|-----------|
| `core/views.py` | Timeline, votación, filtros, signup prompt |
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
| `core/api_views.py` | API para extensión |
| `core/tasks.py` | Celery tasks |
| `core/parse.py` | LLM parsing |
| `core/forms.py` | CustomSignupForm con alias |
| `core/signals.py` | Vote claiming, UserProfile auto-create |
| `browser-extension/` | Chrome/Firefox extension |
