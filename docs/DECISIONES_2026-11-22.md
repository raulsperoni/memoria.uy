# Decisiones de la noche del 21→22/11/2026

Trabajo autónomo mientras dormías. Todo está en la rama `ccr-802fea22-0hs86m`
(sin PR). Cada decisión se puede revertir; las marcadas con ⚠️ conviene que
las mires.

## 1. Modelos de IA

| Uso | Elegido | Por qué |
|---|---|---|
| Historias (hechos + proposiciones) | **Claude Haiku 5.5** → fallback GPT-6-luna → GPT-5-nano | Benchmark con 4 historias reales y 11 modelos: Haiku dio los hechos más completos y precisos y las proposiciones más claras. ~US$0,0018/historia, ~10 s. GPT-5-nano puntuó alto en métricas automáticas pero cometió errores ("Congreso" por Parlamento) y proposiciones con "podría". Gemini 2.5 Flash-Lite estaba rate-limited; DeepSeek y Qwen tardan ~60 s |
| Decisiones tipadas (filtro, verificación, agrupamiento) | **Jev** (`jev-latest` = 1.14) vía OpenRouter | ~0,1 s, calibrado. Funciona con la misma key de OpenRouter (`TYPESAFE_BASE_URL=https://openrouter.ai/api`) |
| Embeddings | Workers AI `bge-m3` | Multilingüe, prácticamente gratis |
| Nombres de burbujas | Haiku 5.5 | Mismo proveedor |

- `core/parse.py` usaba `gemini-2.0-flash-lite-001`, que **ya no existe** en OpenRouter; actualizado.
- No se pasa `temperature`: Haiku 5.5 rechaza valores no default.

## 2. Calibración con datos reales

Lote real: 225 links de 5 medios (El País, El Observador, la diaria,
Montevideo Portal; Subrayado no dio links desde la home).

- **Filtro de interés**: 225 → 51. Umbral bajado de 0,7 a **0,6** porque
  perdía notas de memoria/derechos humanos ("placa de la memoria en el
  Batallón 10", "Maiorano detenido en Sevilla"). En producción el RSS trae
  bajada, lo que mejora la decisión.
- **Medio marcado como "(Uruguay)"** en la pregunta: sin eso "El País + IRPF"
  se leía como España.
- **Agrupamiento**: bge-m3 da solo 0,44–0,54 entre notas del mismo hecho con
  ángulos distintos. Ahora Jev decide en la zona 0,40–0,75 (hasta 3
  candidatas). Jev separa bien: ≈0,03 (no) vs ≈0,9 (sí).
- **Fusión de duplicadas**: nueva `fusionar_duplicadas()` antes de procesar;
  en el lote real unió exactamente los 2 pares duplicados. Nunca fusiona si
  las proposiciones ya tienen votos.
- **Verificación**: cada hecho se chequea contra todas las fuentes de la
  historia (ahora un hecho muestra todos los medios que lo respaldan) y el
  resumen se chequea contra los hechos; si no pasa, se rearma con hechos
  verificados. Jev detecta datos inventados (0,08) pero no errores sutiles de
  conteo (0,67) — limitación conocida.
- **Costo medido**: ~US$0,0024 por historia (Haiku + todas las decisiones Jev).
- **Cloudflare free plan**: rate limit fuerte (30 extracciones = 6,5 min con
  reintentos). ⚠️ Para producción conviene el plan Workers Paid (US$5/mes).

## 3. Se borró la ingesta vieja

Como producción está apagada, eliminé: `browser-extension/`, API de la
extensión, envío manual de URLs, archive.ph/org, proxies gratis,
enriquecimiento de HTML capturado, CORS, `setup-mvp.sh`,
`test_parse_meta.py`. Dependencias fuera: validators, bs4, supabase,
django-cors-headers. Los tests de esos endpoints se borraron.

⚠️ **Se mantuvo** el sistema viejo de `Noticia`/`Voto` (timeline en
`/noticias/`, `/mapa/`, `/clusters/report/`) como legado. Propuesta: borrarlo
cuando exportemos los datos viejos (fase 4).

## 4. Portada y navegación

- `/` = archivo (lo que pasó) con la caja del juego del día arriba.
- Subtítulo: "// Lo que pasó en Uruguay, con fuentes."

## 5. Juego diario (fase 2) — hecho

- 5 proposiciones/día (05:30): máx. 1 por historia y 2 por categoría, al
  menos una "de consenso", y una **recurrente** de semanas anteriores (ancla
  para el clustering).
- Predicción en 5 rangos de 20 %. **El voto propio no cuenta** para evaluar
  la predicción (si no, con pocos votantes alcanzaba con predecir la propia
  opinión).
- Puntaje contra el resultado al cierre del día; racha; tarjeta estilo Wordle
  para WhatsApp / copiar.
- No se puede cambiar el voto.
- Votante anónimo = id en los *datos* de la sesión (Django rota la
  session_key al loguearse); al iniciar sesión los votos pasan a la cuenta.
- También se vota desde la página de cada historia (no suma puntaje).

## 6. Burbujas (fase 3) — hecho

- Reutiliza `core/clustering` (PCA sparsity-aware + grupos por silhouette)
  sobre votos de proposiciones, ventana 60 días, ≥5 votos por persona,
  mínimo 50 personas (`BURBUJAS_MIN_VOTANTES`). Corre 02:15.
- `/burbujas/`: mapa SVG, "lo que nos une", "lo que nos divide", frases
  distintivas de cada burbuja. Tu burbuja aparece en el resultado del juego;
  historia y entidad muestran cómo votó cada burbuja.
- Probado con datos sintéticos: recupera 3 grupos (45/35/20 → 43/35/22,
  silhouette 0,48).
- ⚠️ **Nombres de burbujas con LLM** ("Los Liberales Mano Dura", etc.):
  pueden leerse como etiquetas políticas y generar rechazo. Alternativa:
  solo letras + descripción neutra. Lo dejé activo; decidí vos.

## 7. Hecho después (misma noche)

- **Imágenes OG** generadas en el servidor (historia, nota editada, juego,
  default) con JetBrains Mono (Apache 2.0). Antes el og:image era un SVG, que
  las redes no muestran.
- **PWA**: manifest + service worker mínimo (red primero, caché offline).
- **Datos abiertos** `/datos/`: CSV de historias, hechos con fuentes,
  proposiciones con totales, burbujas y notas editadas. Nunca votos
  individuales.
- **Docker**: no pude construir la imagen acá (el contenedor no llega a los
  mirrors de Debian). El `poetry.lock` es formato 2.1 y el Dockerfile instala
  Poetry 1.6.1: avisa "might not be compatible" pero instala. **Ya era así en
  `main`** antes de mis cambios. ⚠️ Recomiendo subir `POETRY_VERSION` a 2.x en
  el Dockerfile cuando lo puedas probar en Railway.

## 8. Pendiente / para vos

1. ⚠️ Deploy en Railway: cargar variables (ver `archivo/README.md`), crear
   bucket R2 y sus keys, correr `cargar_medios` y `detectar_feeds` (desde acá
   no llego a los sitios de los medios).
2. ⚠️ Plan Workers Paid de Cloudflare (US$5) por el rate limit.
3. Borrado del sistema viejo `Noticia`/`Voto` (fase 4) — antes, exportar sus datos.
5. Revisar el texto legal de "agregador" con alguien que sepa de derecho de cita.

## Capturas

En el scratchpad de la sesión (`shots/`): portada, paso del juego, resultado
de un ítem, resultado del día, historia (TIAR, 3 medios), burbujas, e
imágenes OG (`og-*.png`).
