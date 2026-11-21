# Memoria.uy — segunda vuelta

**Fecha:** noviembre 2026
**Estado:** propuesta, para discutir

## TL;DR

Memoria.uy pasa de "votá noticias que vos mismo subís" a dos cosas que se
alimentan entre sí:

1. **El archivo**: todas las noticias uruguayas, capturadas automáticamente,
   convertidas en *afirmaciones con procedencia*, con historial de cambios.
   Útil aunque nadie entre hoy; imprescindible en momentos políticos.
2. **El juego diario**: 5 afirmaciones del día, de acuerdo / en desacuerdo, y
   adiviná qué opina Uruguay. Trae tráfico y alimenta el clustering.

Se conserva el motor de clustering y las entidades. Se tira la extensión, el
submit manual y los hacks anti-paywall.

---

## 1. Qué aprendimos (2025–2026)

| Supuesto original | Qué pasó |
|---|---|
| La gente va a traer las noticias | No. Curar es trabajo. El submit fue la principal fricción reportada. |
| "Buena / mala noticia" es una señal limpia | Ambigua: ¿buena para quién? ¿el hecho o la cobertura? |
| El clustering va a tener densidad | ~333 votantes, 99% anónimos, noticias que viven un día → matriz muy sparse. |
| "Mirá tu burbuja" retiene | Es curiosidad de una vez, no hábito. |
| Hay que pelear paywalls (extensión, proxies, archive.ph) | Era un problema creado por el diseño de ingesta. |

## 2. Qué aprendimos de resistencia.uy (LUC Comparada)

4,6 M visitas, ~340 mil usuarios, ~4 min promedio, cero pauta.

- **Fuente primaria, no opinión.** Mostraba el texto, no lo que decían de él.
  Lo usaron ambos lados (incluido el gobierno).
- **Un diff.** Lo valioso era *qué cambió*, visualizado simple.
- **Rápido, simple, instalable (PWA).**
- **Distribución:** primero WhatsApp/boca a boca (60% directo), después
  Google (53%, primer resultado para "LUC"). Una página por artículo = SEO.
- **Tráfico en picos** alrededor de momentos políticos, y vivo años después.
- **No neutral, pero transparente** sobre quién lo hace.

**Traducción a memoria.uy:** el archivo es la LUC Comparada de la prensa
(fuente + diff + permalink por cosa), el juego es lo que trae gente entre picos.

## 3. Qué cambió en el mundo

- **Crawling barato** (context.dev, Firecrawl, etc.): ingesta automática de
  todos los medios. Mata el problema de submit.
- **LLMs baratos**: extraer afirmaciones, agrupar la misma historia entre
  medios y resumir cuesta fracciones de centavo por nota.
- **Modelos de decisión** (Jev de TypeSafe y réplicas abiertas): respuestas
  tipadas (sí/no, opción, score), calibradas y rápidas. Buenos para decisiones
  sobre *un* registro; flojos combinando varios.
  - Usarlos para: ¿es noticia uruguaya?, ¿la afirmación es fiel a la fuente?,
    ¿este cambio de titular cambia el sentido?, ¿qué tan divisiva es?
  - No usarlos para: agrupar historias entre medios (eso es embeddings + LLM).

## 4. El producto

### 4.1 El archivo ("resistir el archivo")

- Crawl diario de medios uruguayos (lista curada, ~20–40 sitios).
- Agrupa notas de distintos medios en **Historias** (el mismo hecho).
- Extrae **Afirmaciones**: frases cortas, en nuestras palabras, verificables,
  cada una respaldada por una o más fuentes (procedencia explícita).
- **Historial de cambios:** re-crawl a 24 h y 7 días; diff de titular y
  cuerpo; marca "editada", "cambió el sentido", "despublicada".
- **Timelines por entidad** (persona, organización, lugar): qué se dijo, cuándo,
  quién lo dijo, y cómo reaccionó cada burbuja en ese momento.
- **Página pública por historia, afirmación y entidad** → SEO, permalinks
  citables.

**Copyright / postura:** somos agregador. Lo público son afirmaciones propias,
resúmenes, citas breves y links a la fuente. Los snapshots completos se guardan
de forma **privada** como evidencia (procedencia y diffs), no se republican.
Publicamos un hash del snapshot como prueba. (Validar con alguien que sepa de
derecho de cita uruguayo antes de lanzar.)

### 4.2 El juego diario ("¿Qué piensa Uruguay?")

- Cada día 5 afirmaciones del archivo (elegidas por relevancia + score de
  divisividad).
- Por cada una: **de acuerdo / en desacuerdo / no sé**, y **adiviná qué %
  de Uruguay está de acuerdo**.
- Resultado: tarjeta compartible estilo Wordle ("Leí a Uruguay 4/5").
- Sin cuenta. Cuenta opcional para racha e historial.
- Después de votar: link a la historia en el archivo (fuentes, cambios, entidades).

### 4.3 Clustering y burbujas (se mantiene)

- La unidad de voto pasa de **noticia** a **afirmación**. Las afirmaciones
  sobre temas recurrentes viven semanas → más solapamiento → matriz más densa.
- Mismo pipeline: PCA sparsity-aware, K-Means, jerárquico, consenso, puentes.
- El mapa de burbujas pasa a ser un momento ("mirá dónde caés"), no la home.
- El reporte de consenso / división se vuelve el producto para
  investigadores y periodistas.

## 5. Modelo de datos (borrador)

```
Medio ──< Fuente (nota crawleada) ──< Snapshot (html privado, hash, fecha)
                    │                         └─ Cambio (diff, tipo, score)
                    >── Historia ──< Afirmacion >──< Fuente   (procedencia)
                                         │
                                         ├──< Voto (+ predicción %)
                                         └──< Entidad (vía AfirmacionEntidad)
```

## 6. Qué se reutiliza / qué se tira

**Se queda**
- `core/clustering/*` completo (cambia `matrix_builder` para usar afirmaciones).
- `Entidad`, extracción de entidades, `ClusterNameCache`, modelos de runs.
- Sesiones anónimas + claim de votos al registrarse (`signals.py`).
- Celery + beat, `task_lock`, fallback de modelos en `parse.py`.
- Reporte de investigación y APIs de consenso / puentes / evolución.
- `normalize_url()`.

**Se adapta**
- `Noticia` → `Fuente` (+ `Snapshot`, `Cambio`).
- `Voto` → voto sobre `Afirmacion`, con campo de predicción.
- `parse.py` → extracción de afirmaciones con procedencia.
- Timeline → página del juego diario + páginas del archivo.

**Se tira**
- `browser-extension/`
- Submit manual de URLs
- Captura de HTML desde el cliente, proxies gratis (`url_requests.py`), archive.ph
- Página de stats deprecada

**Migración de datos:** los votos viejos se archivan; no se convierten.

## 7. Fases

1. **Ingesta + archivo (sin votos).** Crawl, historias, afirmaciones, snapshots,
   diffs, páginas públicas por entidad. Medir: cobertura, calidad de
   afirmaciones, costo por día. Ya es útil solo.
2. **Juego diario.** 5 afirmaciones, voto + predicción, tarjeta compartible.
   Medir: retorno a 7 días, shares.
3. **Clustering sobre afirmaciones.** Reconectar el motor y el mapa cuando
   haya densidad (≥ ~300 votantes activos en 30 días).
4. **Para investigadores.** Export abierto, API, reporte periódico.

## 8. Riesgos

- **Calidad de afirmaciones:** una afirmación sesgada o infiel destruye la
  confianza. Mitigación: chequeo de fidelidad automático + procedencia visible
  + botón "reportar".
- **Percepción de sesgo:** el dominio y la elección de afirmaciones van a ser
  leídos políticamente. Mitigación: transparencia del algoritmo de selección,
  como resistencia.uy (no neutral, pero transparente).
- **Costos de crawl** si se escala la cantidad de medios.
- **Legal:** validar postura de agregador.
- **Mantenimiento:** el crawler se rompe cuando los medios cambian el HTML.
  Delegar extracción a un servicio y monitorear.

## 9. Preguntas abiertas

- ¿Qué medios en la lista inicial? ¿Incluir radios/TV con web, cuentas de X/Bluesky?
- ¿Las afirmaciones las elige solo el LLM o hay curación humana liviana?
- ¿Dominio y marca: memoria.uy sigue siendo el nombre?
- ¿Datos abiertos desde el día 1 (como resistencia.uy con Impo)?
