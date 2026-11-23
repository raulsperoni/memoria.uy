"""Tests del clustering que usan las burbujas del juego."""

import numpy as np
from scipy.sparse import lil_matrix

from core.clustering import compute_sparsity_aware_pca, group_clusters


def test_compute_sparsity_aware_pca():
    """Test PCA with sparse matrix."""
    # Create small test matrix
    n_voters = 10
    n_noticias = 5
    vote_matrix = lil_matrix((n_voters, n_noticias), dtype=np.float32)

    # Fill with random votes
    np.random.seed(42)
    for i in range(n_voters):
        for j in range(n_noticias):
            if np.random.rand() > 0.3:  # 70% density
                vote_matrix[i, j] = np.random.choice([-1, 0, 1])

    pca_result = compute_sparsity_aware_pca(vote_matrix, n_components=2)

    # Check output shapes
    assert pca_result["voter_projections"].shape == (n_voters, 2)
    assert pca_result["noticia_projections"].shape == (n_noticias, 2)
    assert len(pca_result["variance_explained"]) == 2
    assert len(pca_result["voter_vote_counts"]) == n_voters
    assert len(pca_result["noticia_vote_counts"]) == n_noticias
    assert all(pca_result["voter_vote_counts"] > 0)


def test_group_clusters():
    """Test hierarchical group clustering."""
    np.random.seed(42)

    # Create base labels (simulate base clustering)
    base_labels = np.random.randint(0, 10, size=50)

    # Create projections
    projections = np.random.randn(50, 2)

    group_labels, best_k, silhouette_scores = group_clusters(
        base_labels, projections, k_range=(2, 4)
    )

    # Check outputs
    assert len(group_labels) == 50
    assert 2 <= best_k <= 4
    assert len(silhouette_scores) > 0
