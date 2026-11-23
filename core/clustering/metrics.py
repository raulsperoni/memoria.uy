"""
Clustering quality and similarity metrics.

Implements consensus scores, voter similarity, and clustering evaluation.

References:
- Rousseeuw, P.J. (1987). "Silhouettes: A graphical aid to the interpretation
  and validation of cluster analysis." J. Computational and Applied
  Mathematics, 20, 53-65. doi:10.1016/0377-0427(87)90125-7

See REFERENCES.md for detailed documentation.
"""

import numpy as np
from sklearn.metrics import silhouette_score
import logging

logger = logging.getLogger(__name__)


def compute_silhouette_score(projections, labels):
    """
    Compute silhouette score for clustering quality.

    Args:
        projections: numpy array (N_voters × 2)
        labels: cluster assignments (N_voters,)

    Returns:
        float: silhouette score (-1 to 1)
            -1 = incorrect clustering
            0 = overlapping clusters
            1 = well-separated clusters
    """
    n_unique_labels = len(np.unique(labels))

    if n_unique_labels < 2:
        logger.warning("Cannot compute silhouette: only 1 cluster")
        return 0.0

    if n_unique_labels >= len(labels):
        logger.warning(
            "Cannot compute silhouette: "
            "too many clusters for sample size"
        )
        return 0.0

    try:
        score = silhouette_score(projections, labels)
        return score
    except Exception as e:
        logger.error(f"Error computing silhouette score: {e}")
        return 0.0


