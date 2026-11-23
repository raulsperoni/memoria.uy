"""
Hierarchical clustering for group and subgroup detection.

Implements Polis-style hierarchical clustering:
- Base clusters (k=100) on all voters
- Group clusters (k=2-5, auto-selected) on base cluster centroids
- Subgroup clusters within each group

References:
- Rousseeuw, P.J. (1987). "Silhouettes: A graphical aid to the interpretation
  and validation of cluster analysis." J. Computational and Applied
  Mathematics, 20, 53-65. doi:10.1016/0377-0427(87)90125-7
- Polis implementation: github.com/compdemocracy/polis
  (math/src/polismath/math/conversation.clj - group-k-smoother)

See REFERENCES.md for detailed documentation.
"""

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import logging

logger = logging.getLogger(__name__)


def group_clusters(
    base_labels,
    projections,
    k_range=(2, 5),
    silhouette_threshold=0.02
):
    """
    Auto-select k for group clustering using silhouette score with parsimony.

    Implements a modified Polis approach:
    - Polis uses a temporal buffer (only switch k after N consecutive runs
      where new k is better). This requires state across runs.
    - We use a score threshold instead: only increase k if silhouette
      improves by more than the threshold. This prefers fewer groups
      when scores are similar (parsimony principle).

    The silhouette coefficient (Rousseeuw, 1987) measures clustering quality:
    - s(i) = (b(i) - a(i)) / max(a(i), b(i))
    - a(i) = mean intra-cluster distance (cohesion)
    - b(i) = mean nearest-cluster distance (separation)
    - Range: -1 (wrong cluster) to +1 (well clustered)

    Args:
        base_labels: array of base cluster assignments (unused, kept for API)
        projections: voter projections (N_voters x 2)
        k_range: tuple (min_k, max_k) for group clustering (default 2-5)
        silhouette_threshold: minimum improvement required to increase k
            (default 0.02). Higher values = stronger preference for fewer
            groups.

    Returns:
        tuple: (group_labels, best_k, silhouette_scores)
            - group_labels: group assignments for each voter
            - best_k: selected number of groups
            - silhouette_scores: dict {k: score}
    """
    min_k, max_k = k_range
    n_voters = projections.shape[0]

    # Ensure valid k range
    max_k = min(max_k, n_voters - 1)
    min_k = max(2, min_k)

    if max_k < min_k:
        logger.warning(
            f"Not enough voters ({n_voters}) for group clustering"
        )
        return np.zeros(n_voters, dtype=int), 1, {}

    logger.info(
        f"Auto-selecting k for group clustering: "
        f"k_range=({min_k}, {max_k}), threshold={silhouette_threshold}"
    )

    # Compute silhouette scores for each k
    silhouette_scores = {}
    models = {}

    for k in range(min_k, max_k + 1):
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(projections)

        score = silhouette_score(projections, labels)
        silhouette_scores[k] = score
        models[k] = (labels, kmeans)

        logger.debug(f"k={k}: silhouette={score:.4f}")

    # Select k with parsimony preference:
    # Start with minimum k, only increase if score improves significantly
    best_k = min_k
    best_score = silhouette_scores[min_k]

    for k in range(min_k + 1, max_k + 1):
        improvement = silhouette_scores[k] - best_score
        if improvement > silhouette_threshold:
            logger.debug(
                f"k={k} improves by {improvement:.4f} > {silhouette_threshold}"
            )
            best_k = k
            best_score = silhouette_scores[k]
        else:
            logger.debug(
                f"k={k} improves by {improvement:.4f} <= {silhouette_threshold}"
                f" (not enough, keeping k={best_k})"
            )

    logger.info(
        f"Selected k={best_k} (silhouette={best_score:.4f}) "
        f"from scores: {silhouette_scores}"
    )

    group_labels, _ = models[best_k]
    return group_labels, best_k, silhouette_scores


