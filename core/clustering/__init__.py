"""
Polis-style clustering for voter analysis.

This module implements clustering algorithms to identify voting patterns
and group voters based on their opinions on news articles.
"""

from .matrix_builder import build_vote_matrix
from .pca import compute_sparsity_aware_pca
from .kmeans import cluster_voters, compute_cluster_sizes
from .hierarchical import (
    group_clusters,
    create_subgroups,
    compute_group_centroids,
)
from .metrics import (
    compute_cluster_consensus,
    compute_voter_similarity,
    compute_silhouette_score,
    compute_cluster_voting_aggregation,
    compute_distance_to_centroid,
    compute_cluster_entities,
)

__all__ = [
    'build_vote_matrix',
    'compute_sparsity_aware_pca',
    'cluster_voters',
    'compute_cluster_sizes',
    'group_clusters',
    'create_subgroups',
    'compute_group_centroids',
    'compute_cluster_consensus',
    'compute_voter_similarity',
    'compute_silhouette_score',
    'compute_cluster_voting_aggregation',
    'compute_distance_to_centroid',
    'compute_cluster_entities',
]
