# Mensajería y Posicionamiento - Memoria.uy

Estrategia de comunicación para usuarios uruguayos.

---

## Propuesta de Valor Central

**Qué hacen:**
"Votá noticias - no solo qué pasó, sino qué pensás de lo que pasó. ¿Buena noticia? ¿Mala noticia? ¿Te da igual?"

**IMPORTANTE:** El voto es sobre **el contenido/evento de la noticia**, NO sobre la calidad del periodismo.

**Por qué deberían:**
1. **Autoconocimiento**: "Descubrí dónde te parás en el panorama mediático uruguayo"
2. **Reconocimiento de patrones**: "Mirá qué noticias nos unen y cuáles nos dividen"
3. **Construcción colectiva de sentido**: "No estás solo - encontrá gente que ve las noticias como vos"

**Qué obtienen:**

**Recompensas inmediatas** (funciona con 1 usuario):
- Expresión sin fricción - votá en 2 segundos, sin registro
- Historial personal - "Mis Votos" te muestra tu perspectiva
- Vista de consenso - mirá si coincidís con la mayoría o no

**Efectos de red** (se desbloquea con escala):
- "Vos estás acá" - visualización de clusters mostrando tu posición
- Descubrí "gente como yo" - encontrá tu burbuja mediática (o escapá de ella)
- Métricas de consenso - qué temas unen a Uruguay, cuáles lo dividen
- Seguimiento de sentimiento por entidad - ¿este político/a es visto positiva o negativamente en diferentes grupos?

---

## Marcos de Mensajería

### Opción 1: Privacidad Primero, Búsqueda de Verdad
**Titular:** "¿Qué piensan REALMENTE los uruguayos sobre las noticias?"

**Pitch:**
"Los medios te dicen qué pasó. Las secciones de comentarios son tóxicas. Las redes sociales son performáticas.

Memoria.uy es diferente: votá anónimamente, mirá patrones, encontrá tu gente. No hace falta perfil. Sin seguimiento. Solo reacciones honestas a las noticias que todos leemos."

**Caso de uso:** "¿Viste esa nota sobre [político]? Votá. Ahora mirá si la mayoría de los uruguayos está de acuerdo con vos - o si estás en una burbuja de opinión minoritaria."

### Opción 2: Construcción Colectiva de Sentido
**Titular:** "No todas las noticias nos dividen. Descubramos cuáles sí."

**Pitch:**
"Hay artículos con los que todos están de acuerdo - buen o mal periodismo, consenso claro. Otros nos dividen 50/50 - ahí es donde vive la conversación real.

Memoria te muestra la diferencia. Votá noticias. Mirá los patrones. Entendé el panorama mediático uruguayo."

**Caso de uso:** "Descubrí qué medios publican contenido divisivo vs. cuáles generan consenso. Seguí entidades (políticos, organizaciones) y mirá si su cobertura mediática polariza o unifica."

### Opción 3: Postura Anti-Algoritmo
**Titular:** "Vos elegís qué importa. Ningún algoritmo decide por vos."

**Pitch:**
"Los feeds de redes sociales te muestran lo que te mantiene scrolleando. Nosotros te mostramos lo que los uruguayos realmente piensan.

Votá anónimamente. Filtrá por consenso, controversia, o solo TUS votos. Sin trucos de engagement. Sin burbuja de filtros (a menos que la quieras)."

**Caso de uso:** "¿Cansado de las cámaras de eco? Usá Memoria para ver qué noticias dividen tu burbuja de las otras - después leé ambos lados."

---

## Implicaciones de Diseño

### Landing Page (Primeros 5 Segundos)
```
[Hero: Tarjeta de noticia simple con 3 botones de voto]

"¿Qué pensás de esta noticia?"
😊 Buena noticia   😐 Me da igual   😞 Mala noticia

[Texto pequeño debajo]
Sin registro. Sin seguimiento. Solo votá.

[Ver últimas noticias ↓]
```

### Después del Primer Voto (Enganche Inmediato)
```
✓ Voto registrado anónimamente

[Mostrar conteo de votos actualizándose en tiempo real]
😊 Buena: 234 personas (45%)
😐 Neutral: 128 personas (25%)
😞 Mala: 156 personas (30%)

Estás con el 45% que piensa que esta es una buena noticia.

[Filtrar: Mostrame artículos así]
```

### Después de 5+ Votos (Adelanto de Efecto de Red)
```
¡Votaste 5 artículos!

[Mini preview de visualización - 3 puntos en un cluster]

"Tendés a coincidir con 2.341 uruguayos más.
¿Querés ver dónde te parás?"

[Crear perfil opcional para sincronizar votos →]
[O seguir votando anónimamente]
```

### Después de Masa Crítica (~50 usuarios, 500+ votos)
```
[Mapa de Clusters]

"Vos estás acá" [punto destacado]

"Estás en un cluster con 234 personas que votan similar.
Entidades top que seguís: [lista]
Noticias más divisivas para tu grupo: [lista]
Temas de consenso en TODOS los grupos: [lista]"
```

---

## Copy para Momentos Clave

### Visitante por primera vez (sin votos):
> "Scrolleá noticias uruguayas. Votá lo que pensás - buena, mala, o neutral. Mirá qué piensan los demás. Eso es todo."

### Después de 1 voto:
> "Votaste. Contó. No hace falta cuenta. Seguí."

### Después de 3 votos:
> "Estás generando un patrón. ¿Querés guardar tus votos en varios dispositivos? [Registro opcional] o [Seguir votando anónimamente]"

### Después de 10 votos:
> "Votaste 10 veces. Estás ayudando a Uruguay a entender su panorama mediático. Gracias."

### Al ver artículo divisivo (50/50):
> "⚠️ Este artículo divide a los uruguayos 50/50. Leé con atención."

### Al ver artículo de consenso (80%+ acuerdo):
> "✓ Consenso amplio: 847 personas coinciden en que esto es [buen/mal] periodismo."

### Al ver página de entidad (ej: un político):
> "Luis Lacalle Pou aparece en 23 artículos. Sentimiento: 45% positivo, 30% neutral, 25% negativo. [Ver desglose por medio]"

---

## Ángulos de Marketing

### Para early adopters (Fase 1):
**"Ayudanos a mapear el panorama mediático uruguayo"**
- Enfatizar rol pionero
- "Sé parte de los primeros 100 usuarios"
- Mostrarles datos crudos, dejarles explorar

### Para news junkies (Fase 2 - extensión de navegador):
**"Votá mientras leés"**
- Votación con un click desde cualquier sitio de noticias
- Construí tu historial personal de sentimiento noticioso
- Evitá paywalls (beneficio implícito, no publicitar)

### Para medios de comunicación (Fase 3 - widgets embebibles):
**"Dejá que los lectores reaccionen más allá de los comentarios"**
- Embebé votación de Memoria en tus artículos
- Mirá cómo reaccionan al contenido que publicás
- Compará el sentimiento de tu audiencia con el promedio nacional

### Para investigadores/activistas (Fase 4 - clustering):
**"Entendé patrones de polarización"**
- ¿Qué temas dividen a Uruguay?
- ¿Qué entidades polarizan?
- ¿Dónde están las oportunidades de consenso?

---

## Opciones de Tagline

1. **Funcional:** "Votá noticias. Mirá qué piensa Uruguay."
2. **Aspiracional:** "Construcción colectiva de sentido para noticias uruguayas."
3. **Provocador:** "No todas las noticias nos dividen. Descubramos cuáles sí."
4. **Simple:** "Votación anónima de artículos periodísticos."
5. **Orientado a misión:** "Mapeando el panorama mediático uruguayo, un voto a la vez."

---

## Recomendación

Empezar con **Opción 1** (Privacidad Primero) porque:
- Aborda el escepticismo del usuario directamente (sin seguimiento, sin registro)
- Promete valor inmediato (mirá qué piensan los demás)
- Sugiere valor futuro (encontrá tu gente)
- Se posiciona contra alternativas tóxicas (comentarios, redes sociales)

**Copy sugerido para landing page:**

```
MEMORIA.UY

¿Qué piensan realmente los uruguayos sobre las noticias?

[Tarjeta de noticia con botones de voto]

Archivá noticias. Votá anónimamente. Descubrí patrones.

[Últimas Noticias ↓]
```

---

## Microcopy Específico para UI

### Botones de Voto
- 😊 Buena (buena noticia - contenido positivo)
- 😐 Neutral (me da igual - ni buena ni mala)
- 😞 Mala (mala noticia - contenido negativo)

**Nota:** El voto refleja tu reacción al CONTENIDO/EVENTO reportado, no a la calidad periodística.

### Filtros
- "Todas las noticias"
- "Mis votos" (requiere sesión activa)
- "Consenso positivo" (80%+ buena)
- "Consenso negativo" (80%+ mala)
- "Divisivo" (40-60% cada lado)

### Formulario de Envío
- Placeholder: "Pegá el link de la noticia acá"
- Botón: "Agregar y Votar"
- Texto de ayuda: "Agregá cualquier artículo de medios uruguayos"

### Estados de Carga
- "Obteniendo información..." (al enviar URL)
- "Registrando voto..." (al votar)
- "Actualizando vista..." (al filtrar)

### Mensajes de Error
- "No pudimos obtener la noticia. ¿El link está bien?"
- "Ya votaste en este artículo. Podés cambiar tu voto."
- "Algo salió mal. Intentá de nuevo."

### Call to Action - Registro Opcional
- **Título:** "¿Querés guardar tus votos?"
- **Descripción:** "Creá una cuenta (opcional) para ver tus votos en cualquier dispositivo"
- **Beneficios:**
  - ✓ Sincronizá votos entre dispositivos
  - ✓ Seguí entidades y temas
  - ✓ Recibí notificaciones de noticias divisivas
  - ✓ Participá en visualizaciones de clusters (próximamente)
- **Nota:** "Tus votos anónimos anteriores se migrarán automáticamente"

---

## Tono y Voz

**Principios:**
- **Directo**: Sin rodeos, al grano
- **Respetuoso**: No condescendiente, no paternalista
- **Transparente**: Explicar cómo funciona, sin trucos
- **Uruguayo**: Usar voseo, referencias locales
- **Sobrio**: Sin emojis excesivos, sin hype artificial

**Ejemplos:**
- ❌ "¡Increíble! ¡Descubrí lo que piensan tus compatriotas!"
- ✓ "Mirá qué piensan otros uruguayos sobre esta noticia"

- ❌ "Nuestra revolucionaria plataforma de análisis de sentimiento..."
- ✓ "Votá noticias. Vemos los patrones juntos."

- ❌ "¡Únete a la comunidad de Memoria!"
- ✓ "Empezá a votar. No hace falta cuenta."

---

**Última actualización:** 29 de diciembre, 2025
**Versión:** MVP 2025
**Próximos pasos:** Testear mensajes con primeros 50 usuarios, iterar según feedback
