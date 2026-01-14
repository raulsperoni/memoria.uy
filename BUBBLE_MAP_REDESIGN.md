# Rediseño del Mapa de Burbujas

## Motivación Principal

El mapa de clusters actual tiene una estética científica/técnica que no comunica bien a usuarios comunes. Queremos transformarlo en un **mapa de burbujas de información** que sea intuitivo y políticamente legible.

### Problemas del diseño actual

1. **Centroides como diamantes rojos**: Concepto matemático que no significa nada para el usuario promedio
2. **Ejes PC1/PC2 con varianza explicada**: Lenguaje técnico innecesario
3. **Escala de colores Viridis**: Estética de paper científico
4. **Puntos aislados**: No transmiten la idea de "burbuja" o "territorio"
5. **Plotly.js**: Limitado para customización visual orgánica

### Objetivos del rediseño

1. **Hacer visible la burbuja**: Mostrar siluetas/contornos en lugar de centroides abstractos
2. **Estética de mapa de fantasía**: Inspirado en mapas de Tolkien, cartografía antigua
3. **Mostrar noticias en el mapa**: Permitir ver qué noticias "pertenecen" a cada territorio
4. **Reducir jerga técnica**: Eliminar referencias a PCA, varianza, etc.

---

## Cambios Técnicos

### 1. Siluetas de Burbujas (en lugar de centroides)

**Motivación**: Un centroide es un punto invisible para el usuario. Una silueta muestra el "territorio" real del grupo.

**Implementación**:
- Usar alpha shapes o convex hull sobre los puntos de cada cluster
- Alpha shapes permiten formas cóncavas más orgánicas
- Biblioteca: `d3-delaunay` en frontend

**Beneficios**:
- Visualiza el tamaño real del grupo
- Muestra solapamientos entre burbujas (interesante políticamente)
- Comunica "territorio" de forma intuitiva

### 2. Estética de Mapa de Fantasía

**Motivación**: Los mapas de fantasía (Tolkien, cartografía medieval) son intuitivos porque usan metáforas territoriales que todos entendemos.

**Elementos visuales**:
- **Gradientes suaves**: Colores tipo topográfico (tierra, océano) en lugar de escalas científicas
- **Bordes orgánicos**: Líneas onduladas, no geométricas perfectas
- **Tipografía cartográfica**: Serif, quizás inclinada, estilo "aquí hay dragones"
- **"Niebla" en zonas vacías**: Sugiere lo desconocido, áreas sin explorar
- **Texturas sutiles**: Papel envejecido, líneas de contorno

**Referentes**:
- Mapas de la Tierra Media
- Mapas antiguos de navegación
- Estilo "Here be dragons"

### 3. Noticias en el Mapa (Biplot PCA Dual)

**Motivación**: Actualmente solo vemos votantes. Mostrar noticias permite:
- Ver qué contenido "pertenece" a cada burbuja
- Entender por qué los votantes están agrupados
- Hacer el mapa más informativo y accionable

**Estrategia matemática - PCA Dual (Opción A)**:

La matriz de votos `V` tiene forma `(n_votantes, n_noticias)`. Al hacer SVD:

```
V = U @ S @ Vt
```

- `U[:, :2] @ diag(S[:2])` → coordenadas de votantes (ya implementado)
- `Vt[:2, :].T @ diag(S[:2])` → coordenadas de noticias (nuevo)

Esto posiciona noticias cerca de los votantes que las votaron positivamente. Es matemáticamente coherente porque ambos viven en el mismo espacio factorial.

**Visualización de noticias**:
- Iconos pequeños o marcadores distintos a votantes
- Hover muestra título de la noticia
- Click lleva a la noticia
- Opción de filtrar por cluster para ver "noticias de esta burbuja"

---

## Cambios de Biblioteca

### De Plotly.js a D3.js

**Motivación**:
- Plotly es excelente para dashboards científicos pero su look es inherentemente "de datos"
- D3 permite control total sobre SVG para lograr la estética deseada
- D3 tiene soporte nativo para:
  - Alpha shapes via `d3-delaunay`
  - Gradientes y filtros SVG (blur, glow)
  - Paths orgánicos con curvas bezier
  - Bindeo de datos flexible

**Trade-offs**:
- Más código que Plotly
- Pero mucha más flexibilidad visual

---

## Plan de Implementación

### Backend

1. **Nuevo modelo `NoticiaProjection`**
   - Campos: run (FK), noticia (FK), projection_x, projection_y
   - Almacena coordenadas PCA de cada noticia por run

2. **Modificar `core/clustering/pca.py`**
   - Cambiar de sklearn PCA a SVD manual para extraer ambos componentes
   - Retornar tanto proyecciones de votantes como de noticias

3. **Actualizar task `update_voter_clusters`**
   - Guardar `NoticiaProjection` objects junto con `VoterProjection`

4. **Extender API `cluster_data_json`**
   - Incluir `news_projections` con id, título, x, y, votos totales

### Frontend

5. **Reemplazar Plotly por D3.js**
   - Crear scatter plot base con D3
   - Bindear datos de votantes y noticias

6. **Implementar siluetas de burbujas**
   - Calcular alpha shapes/convex hull por cluster
   - Dibujar paths con fill semitransparente

7. **Aplicar estética de mapa**
   - Gradientes de color tipo terreno
   - Bordes orgánicos suavizados
   - Tipografía cartográfica
   - Efectos de niebla en zonas vacías

8. **Testing y ajustes**
   - Correr migraciones
   - Regenerar clustering
   - Ajustar visualización con datos reales

---

## Notas Adicionales

- Mantener la funcionalidad de destacar al usuario actual (estrella dorada)
- Considerar modo "explorar noticias" donde el foco son las noticias, no los votantes
- Posible futuro: animaciones de transición cuando cambian los clusters
