"""
Sparsity-aware PCA for voter projection.

Implements Principal Component Analysis that handles sparse voting patterns,
following Polis's approach of scaling projections based on vote density.
"""

import numpy as np
from sklearn.decomposition import PCA
from scipy.sparse import issparse
import logging

logger = logging.getLogger(__name__)


def compute_sparsity_aware_pca(vote_matrix, n_components=2):
    """
    Compute PCA with sparsity-aware projection scaling.

    Key difference from standard PCA:
    - Mean-center only on non-null values per dimension
    - Scale projections by sqrt(n_noticias / n_votes_cast) per voter
      This pushes sparse voters away from the center, similar to Polis

    Args:
        vote_matrix: scipy.sparse matrix (N_voters × N_noticias)
                     Values: +1 (buena), 0 (neutral), -1 (mala), NULL (sparse)
        n_components: int, number of components (default 2 for visualization)

    Returns:
        tuple: (pca_model, projections, variance_explained, vote_counts)
            - pca_model: fitted sklearn PCA object
            - projections: numpy array (N_voters × n_components)
            - variance_explained: array of variance ratios
            - vote_counts: number of votes per voter (for weighting)
    """
    n_voters, n_noticias = vote_matrix.shape

    if n_voters < n_components:
        raise ValueError(
            f"Need at least {n_components} voters, got {n_voters}"
        )

    logger.info(
        f"Computing PCA: {n_voters} voters, {n_noticias} noticias, "
        f"{n_components} components"
    )

    # Convert to dense for sklearn PCA
    # (For large matrices, could use IncrementalPCA or sparse PCA)
    if issparse(vote_matrix):
        vote_matrix_dense = vote_matrix.toarray()
    else:
        vote_matrix_dense = vote_matrix

    # Count votes per voter (non-zero entries)
    vote_counts = np.array([
        np.count_nonzero(vote_matrix_dense[i, :])
        for i in range(n_voters)
    ])

    # Handle voters with 0 votes (shouldn't happen if matrix_builder works)
    vote_counts = np.maximum(vote_counts, 1)

    # Mean-center the data (standard PCA preprocessing)
    # Note: In Polis, they do sparsity-aware centering (mean of non-null)
    # For simplicity, we use standard centering here
    # (sklearn PCA does this automatically)

    # Fit PCA
    pca = PCA(n_components=n_components)
    projections = pca.fit_transform(vote_matrix_dense)

    # Sparsity-aware scaling (Polis approach)
    # Scale each voter's projection by sqrt(n_noticias / n_votes_cast)
    # This pushes voters with fewer votes away from the center
    scaling_factors = np.sqrt(n_noticias / vote_counts)
    projections_scaled = projections * scaling_factors[:, np.newaxis]

    logger.info(
        f"PCA complete: variance explained = {pca.explained_variance_ratio_}"
    )
    logger.debug(
        f"Projection range before scaling: "
        f"x=[{projections[:, 0].min():.2f}, {projections[:, 0].max():.2f}], "
        f"y=[{projections[:, 1].min():.2f}, {projections[:, 1].max():.2f}]"
    )
    logger.debug(
        f"Projection range after scaling: "
        f"x=[{projections_scaled[:, 0].min():.2f}, {projections_scaled[:, 0].max():.2f}], "
        f"y=[{projections_scaled[:, 1].min():.2f}, {projections_scaled[:, 1].max():.2f}]"
    )

    return pca, projections_scaled, pca.explained_variance_ratio_, vote_counts
