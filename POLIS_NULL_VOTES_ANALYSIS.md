# Análisis: Manejo de Votos Nulos vs Neutrales - Polis vs Memoria.uy

## Resumen Ejecutivo

Este documento analiza cómo Polis maneja la distinción entre votos neutrales (explicit "pass") y votos faltantes (missing/null), compara con nuestra implementación actual, y evalúa las implicaciones del cambio propuesto.

## Cómo Polis Maneja los Votos

### Encoding Oficial de Polis

Según la documentación oficial y exports de Polis:

- **`1`** = Agree (Buena noticia)
- **`-1`** = Disagree (Mala noticia)
- **`0`** = Pass (Voto explícito de "pasar" / neutral)
- **Blank/Missing** = No votó (celda vacía en la matriz sparse)

### Distinción Crítica

Polis distingue explícitamente entre:
1. **"Pass" (0)**: El participante vio la noticia y eligió explícitamente "pasar" - esto es información
2. **Missing/Blank**: El participante nunca vio o no interactuó con esa noticia - esto es ausencia de datos

### Implementación en Matrices Sparse

**Problema fundamental**: En scipy sparse matrices (y la mayoría de implementaciones sparse), los valores `0` NO se almacenan automáticamente. Esto significa:

- Si Polis usa `0` para "pass", técnicamente esos valores tampoco se almacenarían en una matriz sparse estándar
- Sin embargo, Polis probablemente:
  - Almacena explícitamente los `0` usando algún mecanismo especial, O
  - Usa un formato que preserva los `0` explícitos, O
  - Consulta la base de datos directamente para distinguir entre `0` (pass) y missing

### Evidencia del Paper "Polis: Scaling Deliberation"

Del paper principal (2021) y documentación:

1. **Sparsity-aware processing**: Polis está diseñado para trabajar con matrices muy sparse donde la mayoría de celdas están vacías
2. **Pass votes son información**: Los votos "pass" se tratan como información útil (indican neutralidad explícita), no como missing data
3. **Missing votes se ignoran**: Los votos faltantes no se cuentan en agregaciones ni en cálculos de consenso

## Nuestro Problema Original

### Antes del Cambio

En nuestra implementación original:

```python
# En metrics.py - ANTES
vote_matrix_dense = vote_matrix.toarray()  # Missing → 0.0
neutral_count = np.sum(votes_array == 0)  # ❌ Cuenta missing como neutral!
```

**Problema**: Al convertir sparse → dense, los valores faltantes se convierten en `0.0`, igual que los votos neutrales explícitos. Esto causaba que:
- Participantes que NO votaron se contaran como si hubieran votado "neutral"
- Las estadísticas de consenso estaban sesgadas
- Los clusters se formaban incorrectamente

## Solución Implementada: Epsilon para Neutral

### Cambio Realizado

```python
# En matrix_builder.py
NEUTRAL_EPSILON = 0.0001
opinion_encoding = {
    'buena': 1.0,
    'neutral': NEUTRAL_EPSILON,  # 0.0001 en lugar de 0.0
    'mala': -1.0,
}

# En metrics.py
# Convertir epsilon de vuelta a 0.0 para neutral
if abs(vote_value - NEUTRAL_EPSILON) < 1e-6:
    vote_value = 0.0
```

### Ventajas

1. ✅ **Distinción clara**: Neutral (epsilon) vs Missing (no almacenado)
2. ✅ **Preservado en sparse**: El epsilon se almacena en la matriz sparse
3. ✅ **Fácil de convertir**: Se convierte de vuelta a `0.0` en agregación
4. ✅ **Compatible con scipy**: Funciona con matrices sparse estándar

### Desventajas y Consideraciones

1. ⚠️ **Hack técnico**: Usar epsilon es un workaround, no la forma "natural"
2. ⚠️ **Precisión numérica**: El epsilon podría afectar cálculos si no se maneja cuidadosamente
3. ⚠️ **No es exactamente Polis**: Polis probablemente no usa epsilon, sino otro mecanismo
4. ⚠️ **Documentación**: Necesitamos documentar bien este hack para futuros desarrolladores

## Alternativas Consideradas

### Opción 1: Consultar Base de Datos Directamente (Rechazada)

```python
# Consultar DB para cada agregación
db_votes = Voto.objects.filter(noticia_id=noticia_id, ...)
```

**Problema**: Muy ineficiente, requiere queries a DB en cada agregación.

### Opción 2: Máscara Separada (No Implementada)

```python
# Mantener una máscara booleana de qué celdas tienen votos
vote_mask = sparse_matrix.copy()
vote_mask.data = np.ones_like(vote_mask.data)  # Solo presencia
```

**Ventaja**: Más explícito, no requiere epsilon
**Desventaja**: Duplica memoria, más complejo

### Opción 3: Formato COO con Valores Explícitos (No Implementada)

```python
# Usar Coordinate format que puede almacenar 0s explícitos
vote_matrix_coo = vote_matrix.tocoo()
# Modificar para preservar 0s
```

**Problema**: scipy sparse automáticamente elimina 0s incluso en COO.

### Opción 4: Epsilon (Implementada) ✅

La solución actual es pragmática y funciona bien.

## Implicaciones del Cambio

### Impacto en Estadísticas

**Antes**:
- Total de votos = Votos explícitos + No-votos (contados como neutral)
- Consenso sesgado hacia "neutral" artificialmente

**Después**:
- Total de votos = Solo votos explícitos (buena, mala, neutral)
- Consenso basado solo en votos reales
- Más preciso y alineado con Polis

### Impacto en Clustering

**Antes**:
- Votantes con muchos "no-votos" aparecían como muy "neutrales"
- Clusters se formaban incorrectamente basados en sparsity, no en opinión

**Después**:
- Clusters se forman solo sobre votos explícitos
- Similaridad entre votantes basada en co-votos reales
- Más alineado con el enfoque de Polis

### Impacto en PCA

**Antes**:
- Mean-centering incluía muchos 0s artificiales (missing)
- Proyecciones sesgadas

**Después**:
- Mean-centering solo sobre votos reales
- Proyecciones más precisas

## Comparación con Polis

| Aspecto | Polis | Memoria.uy (Antes) | Memoria.uy (Ahora) |
|---------|-------|-------------------|-------------------|
| Encoding neutral | `0` (explícito) | `0` (confundido con missing) | `0.0001` (epsilon) |
| Missing votes | Blank (no almacenado) | `0` (confundido con neutral) | Blank (no almacenado) ✅ |
| Almacenamiento | Probablemente DB + sparse | Sparse (perdía distinción) | Sparse (preserva con epsilon) |
| Agregación | Solo votos explícitos | Incluía missing como neutral ❌ | Solo votos explícitos ✅ |
| Consenso | Basado en votos reales | Sesgado | Basado en votos reales ✅ |

## Recomendaciones

### Corto Plazo (Actual)

1. ✅ **Mantener solución epsilon**: Funciona bien y es pragmática
2. ✅ **Documentar bien**: Asegurar que todos entiendan el hack
3. ✅ **Tests comprehensivos**: Verificar que las estadísticas sean correctas

### Mediano Plazo

1. **Investigar implementación real de Polis**: Revisar código fuente de Polis para ver cómo manejan esto exactamente
2. **Considerar máscara separada**: Si el epsilon causa problemas, migrar a máscara booleana
3. **Benchmarking**: Comparar resultados con datos de Polis reales si es posible

### Largo Plazo

1. **Refactorizar si necesario**: Si encontramos mejor solución, refactorizar
2. **Contribuir a Polis**: Si encontramos mejoras, considerar contribuir de vuelta

## Referencias

1. **Polis Documentation**: https://compdemocracy.org/export/
2. **Polis Paper (2021)**: "Polis: Scaling Deliberation by Mapping High Dimensional Opinion Spaces"
3. **Polis GitHub**: https://github.com/compdemocracy/polis
4. **Research on Missing Votes**: "Representation with Incomplete Votes" (2022)

## Conclusión

El cambio implementado (usar epsilon para neutral) es una solución pragmática que:
- ✅ Corrige el bug crítico de contar missing como neutral
- ✅ Alinea nuestro comportamiento con la filosofía de Polis
- ✅ Es implementable con scipy sparse estándar
- ⚠️ Requiere documentación cuidadosa del hack

**Recomendación**: Mantener la solución actual, pero documentarla extensivamente y monitorear si causa problemas numéricos en el futuro.
