# Memoria.uy - Visión de Producto

**Votá noticias. Descubrí patrones. Salí de tu burbuja.**

## Qué es

Memoria.uy es una herramienta para votar noticias uruguayas. Te permite
expresar qué pensás sobre el contenido de los artículos que leés —si te
parece buena o mala noticia— y ver qué opinan otras personas.

Es un proyecto académico y de interés social. No es un producto comercial.

## Por qué existe

Las noticias nos impactan de diferentes maneras. El mismo artículo puede ser
visto como buena noticia por algunas personas y como mala noticia por otras.

Nos interesa entender estos patrones:
- ¿Qué noticias generan consenso en Uruguay?
- ¿Cuáles nos dividen?
- ¿Existen burbujas de opinión claramente diferenciadas?

Memoria.uy busca hacer visible el panorama mediático uruguayo desde la
perspectiva de quienes leen las noticias, no solo de quienes las producen.

## Problema que resuelve

1. **Cámaras de eco**: Las redes sociales refuerzan lo que ya creés
2. **Paywalls**: El contenido de calidad está fragmentado detrás de muros
3. **Falta de contexto**: No sabés si tu opinión es mayoritaria o minoritaria
4. **Privacidad**: Otros sistemas requieren cuenta y rastrean tu actividad

## Cómo funciona

### 1. Captura de contenido
Cuando agregás una URL (desde el sitio web o la extensión del navegador),
el sistema captura el contenido del artículo para poder procesarlo.

### 2. Votación
Podés votar si el contenido te parece buena noticia, mala noticia, o neutral.
No hace falta registro. Tu voto se guarda de forma anónima usando tu sesión
del navegador.

### 3. Procesamiento
El sistema usa modelos de lenguaje (LLMs) para extraer información del
artículo: título, resumen, entidades mencionadas (personas, organizaciones,
lugares) y sentimiento general.

### 4. Clustering
El sistema agrupa votantes por patrones de voto similares, revelando
"burbujas" de opinión. Podés ver tu posición en el mapa y filtrar noticias
por consenso de tu cluster.

## Usuarios objetivo

- Uruguayos interesados en noticias locales
- Personas que quieren entender otras perspectivas
- Investigadores de opinión pública
- Periodistas buscando feedback sobre cobertura

## Principios de diseño

### Privacidad primero
- No hace falta crear cuenta para votar
- Los votos se vinculan a tu sesión del navegador, no a tu identidad
- No hay tracking entre sitios
- Los IDs de sesión son UUIDs sin relación a identidad

### Monochrome brutalist
- Paleta: blanco y negro exclusivamente
- Tipografía: IBM Plex Mono
- Estética de terminal/código

### Mobile-friendly
- HTMX para actualizaciones parciales
- Diseño responsivo con Tailwind
- Funciona sin JavaScript (degradación graceful)

## Estado actual

### Implementado
- [x] Votación anónima web y extensión
- [x] Extensión Chrome/Firefox (Manifest V3)
- [x] Enriquecimiento con LLM (título, resumen, entidades)
- [x] Clustering Polis-style (PCA + K-Means + silhouette)
- [x] Visualización interactiva de clusters
- [x] Filtro por consenso de cluster ("mi burbuja")
- [x] Sincronización de sesión extensión ↔ web

### Próximo
- [ ] Rediseño del mapa (estilo cartográfico, no scatter plot)
- [ ] Noticias proyectadas en el mapa de clusters
- [ ] Scheduler automático de clustering (Celery beat)
- [ ] Métricas de polarización

### Futuro
- [ ] Seguimiento temporal de entidades (evolución de sentimiento)
- [ ] Recomendaciones basadas en cluster
- [ ] Bridge-builder detection (votantes que conectan clusters)
- [ ] API pública para investigadores

## Limitaciones actuales

- La votación refleja tu opinión sobre el **contenido/evento** de la noticia,
  no sobre la calidad del periodismo
- El procesamiento con LLMs puede tomar algunos minutos. No siempre es perfecto
- Este es un proyecto en desarrollo activo. Algunas funciones pueden cambiar

## Métricas de éxito

- Usuarios únicos por semana
- Votos por día
- Diversidad de clusters
- Retención de sesiones
- Cobertura de medios uruguayos

## Documentación relacionada

- [README.md](README.md) - Documentación técnica
- [docs/SCIENTIFIC.md](docs/SCIENTIFIC.md) - Algoritmos y referencias científicas

## Contacto

- Web: https://memoria.uy
- Código: https://github.com/raulsperoni/memoria.uy
