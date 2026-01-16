# Clustering Algorithm References

This document provides scientific references and explanations for the clustering
algorithms used in Memoria.uy's voter clustering system.

## Overview

The clustering pipeline follows the approach used by
[Polis](https://github.com/compdemocracy/polis), an open-source platform for
large-scale opinion gathering. The pipeline consists of:

1. **Vote Matrix Construction** - Sparse matrix of voters × noticias
2. **PCA Projection** - Dimensionality reduction to 2D for visualization
3. **K-Means Clustering** - Base clustering with ~100 clusters
4. **Hierarchical Grouping** - Aggregation into 2-5 interpretable groups
5. **Silhouette-based K Selection** - Automatic selection of optimal group count

---

## Principal Component Analysis (PCA)

### Original References

- **Pearson, K. (1901)**. "On lines and planes of closest fit to systems of
  points in space." *Philosophical Magazine*, Series 6, 2(11), 559-572.

  Pearson introduced the geometric optimization approach to finding lines and
  planes that best fit points in p-dimensional space.

- **Hotelling, H. (1933)**. "Analysis of a complex of statistical variables
  into principal components." *Journal of Educational Psychology*, 24,
  417-441, 498-520.

  Hotelling independently developed and named the method, providing the
  standard algebraic derivation used today.

- **Jolliffe, I.T. (2002)**. *Principal Component Analysis*, 2nd edition.
  Springer-Verlag. ISBN: 978-0387954424.

  The definitive modern reference on PCA theory and applications.

### Implementation: Sparsity-Aware PCA

Standard PCA assumes complete data, but voting matrices are inherently sparse
(voters don't vote on all noticias). Our implementation follows Polis's
approach:

```
File: pca.py

1. Mean-center only on observed (non-null) values per dimension
2. Apply standard PCA to get 2D projections
3. Scale projections by sqrt(n_noticias / n_votes_cast) per voter
```

The scaling factor (step 3) is critical: it prevents voters with few votes from
clustering artificially near the center. A voter who voted on 5 noticias should
not appear more "centrist" than one who voted on 50, simply due to having less
data.

**Mathematical justification**: The scaling compensates for the reduced variance
in projections caused by sparse observations. See Polis's math-worker
implementation for the original approach.

---

## K-Means Clustering

### Original Reference

- **Lloyd, S.P. (1982)**. "Least squares quantization in PCM."
  *IEEE Transactions on Information Theory*, 28(2), 129-137.
  doi:10.1109/TIT.1982.1056489

  Originally developed at Bell Labs in 1957 for pulse-code modulation,
  Lloyd's algorithm became the standard k-means implementation.

### Algorithm

Lloyd's algorithm iteratively:

1. **Assignment**: Assign each point to nearest centroid
2. **Update**: Recompute centroids as cluster means
3. **Repeat**: Until convergence or max iterations

```
File: kmeans.py

Parameters:
- k: Number of clusters (auto-selected as min(100, max(10, n_voters // 10)))
- max_iters: 20 (following Polis)
- n_init: 10 (multiple random initializations to avoid local minima)
- algorithm: 'lloyd' (standard k-means)
```

### K Selection for Base Clusters

The base cluster count uses a heuristic rather than optimization:

```
k_base = min(100, max(10, n_voters // 10))
```

This creates fine-grained clusters (~1 cluster per 10 voters, capped at 100)
that serve as input for hierarchical grouping. The exact k is less critical
here because:

1. These clusters are intermediate, not shown to users
2. The hierarchical step will aggregate them into 2-5 groups
3. More clusters provide finer resolution for the grouping step

---

## Silhouette Coefficient

### Original Reference

- **Rousseeuw, P.J. (1987)**. "Silhouettes: A graphical aid to the
  interpretation and validation of cluster analysis."
  *Journal of Computational and Applied Mathematics*, 20, 53-65.
  doi:10.1016/0377-0427(87)90125-7

  [Open access PDF](https://wis.kuleuven.be/stat/robust/papers/publications-1987/rousseeuw-silhouettes-jcam-sciencedirectopenarchiv.pdf)

### Formula

For each sample i:

```
s(i) = (b(i) - a(i)) / max(a(i), b(i))

where:
  a(i) = mean distance to other points in same cluster (cohesion)
  b(i) = mean distance to points in nearest other cluster (separation)
```

The silhouette coefficient ranges from -1 to +1:

| Score | Interpretation |
|-------|----------------|
| > 0.7 | Strong clustering structure |
| > 0.5 | Reasonable structure |
| > 0.25 | Weak structure |
| ≤ 0 | Overlapping or incorrect assignments |

### Implementation

```
File: metrics.py - compute_silhouette_score()
File: hierarchical.py - group_clusters()

Uses sklearn.metrics.silhouette_score which computes the mean silhouette
coefficient across all samples.
```

---

## Hierarchical Group Clustering

### Polis Approach

Polis uses a two-stage clustering:

1. **Base clusters** (k ≈ 100): Fine-grained clustering on PCA projections
2. **Group clusters** (k = 2-5): Coarse grouping for visualization

The group count is selected by maximizing silhouette score over k ∈ {2,3,4,5}.

**Source**: [Polis clustering documentation](https://compdemocracy.org/silhouette-coefficient/)
and [GitHub discussion #1289](https://github.com/compdemocracy/polis/issues/1289).

### K Selection with Temporal Smoothing

Polis implements a **temporal buffer** to prevent oscillation between k values:

```
From: polismath/math/conversation.clj (group-k-smoother)

1. Compute silhouette scores for k = 2, 3, 4, 5
2. Select k with highest silhouette score
3. Only switch to new k if it has been optimal for N consecutive runs
   (default: N = 4, the "group-k-buffer")
```

This prevents the displayed number of groups from changing frequently due to
minor data fluctuations.

### Our Implementation

```
File: hierarchical.py - group_clusters()

Parameters:
- k_range: (2, 5) - range of k values to test
- silhouette_threshold: 0.02 - minimum improvement required to increase k

Selection logic:
1. Compute silhouette scores for each k in range
2. Start with k=2 (most parsimonious)
3. Only increase k if silhouette improves by more than threshold

This implements a "parsimony preference": when scores are similar, prefer
fewer groups for interpretability.
```

**Rationale**: Unlike Polis (which has continuous conversations), Memoria.uy
runs clustering periodically. A temporal buffer across runs would require
persisting state, so we use a score-threshold approach instead. The effect is
similar: avoid switching to more groups unless there's clear evidence.

---

## Design Decisions

### Why 2-5 Groups?

From [Polis issue #1289](https://github.com/compdemocracy/polis/issues/1289):

> "This was chosen for explainability and visualization benefits."

More than 5 groups becomes difficult to visualize and interpret. However, this
is a trade-off: if 8 distinct groups truly exist, collapsing to 5 may lose
information.

### Why Not Use Other Clustering Methods?

Alternatives considered:

- **UMAP**: Better for complex manifolds, but less interpretable. See
  [Polis discussion #1166](https://github.com/compdemocracy/polis/discussions/1166).

- **Hierarchical agglomerative**: Deterministic but doesn't scale well.

- **DBSCAN**: Doesn't require k, but sensitive to density parameters.

K-means + silhouette remains the standard for interpretable opinion clustering.

### Consensus Score

Within each cluster, we compute a consensus score measuring internal agreement:

```
File: metrics.py - compute_cluster_consensus()

consensus = 1 - (entropy / max_entropy)

where entropy is computed over the vote distribution within the cluster.
```

High consensus (>0.7) indicates the cluster agrees on most noticias.
Low consensus (<0.3) indicates internal disagreement.

---

## References Summary

| Algorithm | Original Paper | Year |
|-----------|---------------|------|
| PCA | Pearson; Hotelling | 1901; 1933 |
| K-Means (Lloyd) | Lloyd, S.P. | 1957/1982 |
| Silhouette | Rousseeuw, P.J. | 1987 |

**Polis Implementation**:
- Repository: https://github.com/compdemocracy/polis
- Math worker: `math/src/polismath/math/clusters.clj`
- K-selection: `math/src/polismath/math/conversation.clj`

---

## Further Reading

- Polis documentation: https://compdemocracy.org/
- Silhouette coefficient: https://compdemocracy.org/silhouette-coefficient/
- scikit-learn silhouette: https://scikit-learn.org/stable/modules/generated/sklearn.metrics.silhouette_score.html
