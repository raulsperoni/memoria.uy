# Documentación Científica

Referencias y explicaciones de los algoritmos de clustering usados en
Memoria.uy, basados en [Polis](https://github.com/compdemocracy/polis).

## Pipeline de Clustering

```
Votos → Matriz sparse → PCA 2D → K-Means base → Agrupación jerárquica
```

1. **Matriz de votos**: Sparse matrix (votantes × noticias)
   - buena = +1, neutral = 0.0001 (epsilon), mala = -1
   - Celdas vacías = no votó (no almacenado)

2. **PCA Sparsity-Aware**: Proyección 2D con escalado por sparsity

3. **K-Means base**: ~100 clusters (k = min(100, max(10, n_voters // 10)))

4. **Agrupación jerárquica**: 2-5 grupos usando silhouette score

5. **Métricas de consenso**: Acuerdo intra-cluster (0-1)

---

## Principal Component Analysis (PCA)

### Referencias

- **Pearson, K. (1901)**. "On lines and planes of closest fit to systems of
  points in space." *Philosophical Magazine*, Series 6, 2(11), 559-572.

- **Hotelling, H. (1933)**. "Analysis of a complex of statistical variables
  into principal components." *Journal of Educational Psychology*, 24,
  417-441, 498-520.

- **Jolliffe, I.T. (2002)**. *Principal Component Analysis*, 2nd edition.
  Springer-Verlag. ISBN: 978-0387954424.

### Implementación Sparsity-Aware

PCA estándar asume datos completos. Las matrices de votación son sparse
(votantes no votan en todas las noticias). Nuestra implementación sigue
el enfoque de Polis:

```
Archivo: core/clustering/pca.py

1. Mean-center solo sobre valores observados (no nulos) por dimensión
2. Aplicar PCA estándar para proyección 2D
3. Escalar proyecciones por sqrt(n_noticias / n_votos_emitidos) por votante
```

El factor de escalado (paso 3) es crítico: previene que votantes con pocos
votos se agrupen artificialmente cerca del centro.

---

## K-Means Clustering

### Referencia

- **Lloyd, S.P. (1982)**. "Least squares quantization in PCM."
  *IEEE Transactions on Information Theory*, 28(2), 129-137.
  doi:10.1109/TIT.1982.1056489

### Algoritmo

Lloyd's algorithm itera:

1. **Asignación**: Asignar cada punto al centroide más cercano
2. **Actualización**: Recalcular centroides como media del cluster
3. **Repetir**: Hasta convergencia o max iteraciones

```
Archivo: core/clustering/kmeans.py

Parámetros:
- k: Número de clusters (auto-seleccionado)
- max_iters: 20 (siguiendo Polis)
- n_init: 10 (múltiples inicializaciones)
- algorithm: 'lloyd'
```

---

## Silhouette Coefficient

### Referencia

- **Rousseeuw, P.J. (1987)**. "Silhouettes: A graphical aid to the
  interpretation and validation of cluster analysis."
  *Journal of Computational and Applied Mathematics*, 20, 53-65.
  doi:10.1016/0377-0427(87)90125-7

### Fórmula

Para cada muestra i:

```
s(i) = (b(i) - a(i)) / max(a(i), b(i))

donde:
  a(i) = distancia media a otros puntos del mismo cluster (cohesión)
  b(i) = distancia media a puntos del cluster más cercano (separación)
```

| Score | Interpretación |
|-------|----------------|
| > 0.7 | Estructura fuerte |
| > 0.5 | Estructura razonable |
| > 0.25 | Estructura débil |
| ≤ 0 | Solapamiento o asignaciones incorrectas |

---

## Clustering Jerárquico

Polis usa clustering de dos etapas:

1. **Clusters base** (k ≈ 100): Clustering fino sobre proyecciones PCA
2. **Clusters grupo** (k = 2-5): Agrupación gruesa para visualización

El número de grupos se selecciona maximizando silhouette sobre k ∈ {2,3,4,5}.

```
Archivo: core/clustering/hierarchical.py

Parámetros:
- k_range: (2, 5)
- silhouette_threshold: 0.02 (mejora mínima para aumentar k)

Lógica de selección:
1. Calcular silhouette para cada k en rango
2. Empezar con k=2 (más parsimonioso)
3. Solo aumentar k si silhouette mejora más que threshold
```

---

## Manejo de Votos Neutrales vs Missing

### Problema

En matrices sparse, los valores 0 no se almacenan. Esto confunde votos
neutrales explícitos (el usuario eligió "neutral") con votos faltantes
(el usuario nunca vio la noticia).

### Solución: Epsilon

```python
# core/clustering/matrix_builder.py
NEUTRAL_EPSILON = 0.0001

opinion_encoding = {
    'buena': 1.0,
    'neutral': NEUTRAL_EPSILON,  # 0.0001 en lugar de 0.0
    'mala': -1.0,
}
```

En agregación, el epsilon se convierte de vuelta a 0.0.

### Comparación con Polis

| Aspecto | Polis | Memoria.uy |
|---------|-------|------------|
| Neutral | 0 (explícito) | 0.0001 (epsilon) |
| Missing | Blank | Blank |
| Almacenamiento | DB + sparse | Sparse con epsilon |

---

## Métricas de Consenso

```
Archivo: core/clustering/metrics.py

consensus = 1 - (entropy / max_entropy)

donde entropy se calcula sobre la distribución de votos en el cluster.
```

- Consenso alto (>0.7): El cluster está de acuerdo en la mayoría de noticias
- Consenso bajo (<0.3): Desacuerdo interno

---

## Referencias de Polis

- **Repositorio**: https://github.com/compdemocracy/polis
- **Math worker**: `math/src/polismath/math/clusters.clj`
- **K-selection**: `math/src/polismath/math/conversation.clj`
- **Documentación**: https://compdemocracy.org/
- **Silhouette**: https://compdemocracy.org/silhouette-coefficient/

---

## Resumen de Referencias

| Algoritmo | Paper | Año |
|-----------|-------|-----|
| PCA | Pearson; Hotelling | 1901; 1933 |
| K-Means (Lloyd) | Lloyd, S.P. | 1957/1982 |
| Silhouette | Rousseeuw, P.J. | 1987 |
