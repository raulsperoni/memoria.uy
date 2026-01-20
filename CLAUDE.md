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

### Analytics page (`/clusters/stats/`)
Página completa de estadísticas con múltiples secciones:

**1. Usuarios y Actividad**
- Total de usuarios registrados
- Nuevos usuarios (7d y 30d)
- Usuarios activos (votaron o enviaron news en 30d)
- Votantes únicos (incluye anónimos con session_key)
- Gráficos: nuevos usuarios por día, noticias enviadas por día

**2. Actividad de Votación**
- Total de votos, últimos 7d, últimos 30d
- Gráfico de votos por día (últimos 30d)
- Breakdown por opinión (buena/mala/neutral)

**3. Evolución de Burbujas** (Sankey diagram)
- API: `/api/clustering/evolution/?runs=N` (default: 5, max: 20)
- Compara membresías entre corridas consecutivas
- Clasifica relaciones: continuation (>80%), split, merge, minor (<20%)
- Selector de rango: 3, 5, 10, 15 corridas
- Visualización interactiva con Plotly (hover, drag)
- Datos históricos completos en `VoterClusterMembership` y `VoterClusterRun`

**4. Resumen de Clustering**
- Número de burbujas, última actualización, tiempo de cómputo
- Total de votantes en último clustering

**5. Detalle por Burbuja**
- Tamaño, consenso promedio, centroide
- Entidades vistas positiva/negativamente
- Top noticias con mayor consenso

Ver `ClusterStatsView` en [core/views_clustering.py](core/views_clustering.py).
Análisis técnico de evolución en [docs/CLUSTER_EVOLUTION_ANALYSIS.md](docs/CLUSTER_EVOLUTION_ANALYSIS.md).

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
| `core/views_clustering.py` | Mapa de burbujas, stats page (users/activity/clustering), evolution API |
| `core/templates/clustering/stats.html` | Analytics: usuarios, actividad, votos, clusters, evolución |
| `core/api_views.py` | API para extensión |
| `core/tasks.py` | Celery tasks |
| `core/parse.py` | LLM parsing |
| `core/forms.py` | CustomSignupForm con alias |
| `core/signals.py` | Vote claiming, UserProfile auto-create |
| `core/clustering/` | Motor matemático |
| `browser-extension/` | Chrome/Firefox extension |
