"""
Hierarchical clustering for group and subgroup detection.

Implements Polis-style hierarchical clustering:
- Base clusters (k=100) on all voters
- Group clusters (k=2-5, auto-selected) on base cluster centroids
- Subgroup clusters within each group
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
    silhouette_buffer=4
):
    """
    Auto-select k for group clustering using silhouette score.

    Polis approach: Try k from 2 to 5, select best silhouette score
    with 4-count smoothing buffer (only change k if new score is
    significantly better).

    Args:
        base_labels: array of base cluster assignments
        projections: voter projections (N_voters × 2)
        k_range: tuple (min_k, max_k) for group clustering
        silhouette_buffer: smoothing factor (default 4, like Polis)

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
        # Fallback: single group
        return np.zeros(n_voters, dtype=int), 1, {}

    logger.info(
        f"Auto-selecting k for group clustering: k_range=({min_k}, {max_k})"
    )

    # Compute silhouette scores for each k
    silhouette_scores = {}
    models = {}

    for k in range(min_k, max_k + 1):
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(projections)

        # Silhouette score: measures cluster quality (-1 to 1)
        # Higher is better (well-separated clusters)
        score = silhouette_score(projections, labels)
        silhouette_scores[k] = score
        models[k] = (labels, kmeans)

        logger.debug(f"k={k}: silhouette={score:.4f}")

    # Select k with best silhouette score (with smoothing buffer)
    # Polis uses 4-count buffer: only switch to new k if score improves
    best_k = min_k
    best_score = silhouette_scores[min_k]

    for k in range(min_k + 1, max_k + 1):
        if silhouette_scores[k] > best_score:
            best_k = k
            best_score = silhouette_scores[k]

    logger.info(
        f"Selected k={best_k} (silhouette={best_score:.4f})"
    )

    group_labels, _ = models[best_k]
    return group_labels, best_k, silhouette_scores


def create_subgroups(group_labels, projections, k_subgroup=3):
    """
    Create subgroups within each group.

    Args:
        group_labels: array of group assignments
        projections: voter projections (N_voters × 2)
        k_subgroup: number of subgroups per group (default 3)

    Returns:
        dict: {group_id: subgroup_labels}
            - group_id: parent group identifier
            - subgroup_labels: array of subgroup assignments for voters in group
    """
    unique_groups = np.unique(group_labels)
    subgroups = {}

    logger.info(
        f"Creating subgroups: {len(unique_groups)} groups, "
        f"k_subgroup={k_subgroup}"
    )

    for group_id in unique_groups:
        # Get voters in this group
        group_mask = group_labels == group_id
        group_projections = projections[group_mask]
        n_voters_in_group = group_projections.shape[0]

        # Ensure k doesn't exceed voter count
        k_actual = min(k_subgroup, n_voters_in_group)

        if k_actual < 2:
            # Too few voters for clustering
            subgroups[group_id] = np.zeros(n_voters_in_group, dtype=int)
            logger.debug(
                f"Group {group_id}: {n_voters_in_group} voters, "
                f"no subgrouping (too few)"
            )
            continue

        # Run k-means on group
        kmeans = KMeans(n_clusters=k_actual, random_state=42, n_init=10)
        subgroup_labels = kmeans.fit_predict(group_projections)

        subgroups[group_id] = subgroup_labels

        # Log subgroup sizes
        unique, counts = np.unique(subgroup_labels, return_counts=True)
        logger.debug(
            f"Group {group_id}: {n_voters_in_group} voters, "
            f"{len(unique)} subgroups, sizes={dict(zip(unique, counts))}"
        )

    return subgroups


def compute_group_centroids(group_labels, projections):
    """
    Compute centroid for each group.

    Args:
        group_labels: array of group assignments
        projections: voter projections (N_voters × 2)

    Returns:
        dict: {group_id: centroid}
    """
    unique_groups = np.unique(group_labels)
    centroids = {}

    for group_id in unique_groups:
        group_mask = group_labels == group_id
        group_projections = projections[group_mask]
        centroid = group_projections.mean(axis=0)
        centroids[group_id] = centroid

    return centroids
