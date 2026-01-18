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
- `Voto`: Opinión de usuario sobre noticia
- `Entidad`: Personas, organizaciones, lugares extraídos
- `VoterCluster*`: Modelos de clustering (Run, Cluster, Projection, etc.)

### Sesiones

Prioridad de identificación de votante:
1. Usuario autenticado → `usuario` field
2. Extensión → header `X-Extension-Session` o cookie `memoria_extension_session`
3. Django session → `session_key`

Ver `get_voter_identifier()` en [core/views.py](core/views.py).

## Patrones importantes

### Task locking
Todos los Celery tasks usan `@task_lock(timeout=...)` para prevenir ejecución
duplicada.

### Model fallback en AI parsing
Si el modelo primario falla, automáticamente intenta el siguiente en prioridad.
Ver [core/parse.py](core/parse.py).

### Clustering Polis-style
Motor matemático en `core/clustering/`. Ver [docs/SCIENTIFIC.md](docs/SCIENTIFIC.md)
para detalles de algoritmos.

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
| `core/views.py` | Timeline, votación, filtros |
| `core/views_clustering.py` | Vistas del mapa de burbujas + OG images |
| `core/api_views.py` | API para extensión |
| `core/tasks.py` | Celery tasks |
| `core/parse.py` | LLM parsing |
| `core/clustering/` | Motor matemático |
| `browser-extension/` | Chrome/Firefox extension |
