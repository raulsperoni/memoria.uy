"""
Sparsity-aware PCA for voter and noticia projection (biplot).

Implements Principal Component Analysis that handles sparse voting patterns,
following Polis's approach of scaling projections based on vote density.

Uses SVD to project both voters (rows) and noticias (columns) into the
same 2D space for biplot visualization.

References:
- Pearson, K. (1901). "On lines and planes of closest fit to systems of
  points in space." Philosophical Magazine, Series 6, 2(11), 559-572.
- Hotelling, H. (1933). "Analysis of a complex of statistical variables
  into principal components." J. Educational Psychology, 24, 417-441.
- Jolliffe, I.T. (2002). Principal Component Analysis, 2nd ed. Springer.
- Polis implementation: github.com/compdemocracy/polis
  (math/src/polismath/math/pca.clj)

See REFERENCES.md for detailed documentation.
"""

import numpy as np
from scipy.sparse import issparse
from scipy.linalg import svd
import logging

logger = logging.getLogger(__name__)


def compute_sparsity_aware_pca(vote_matrix, n_components=2):
    """
    Compute PCA with sparsity-aware projection scaling using SVD.

    Uses SVD decomposition V = U @ S @ Vt to project both voters and
    noticias into the same space (biplot):
    - Voters: U[:, :k] @ diag(S[:k])
    - Noticias: Vt[:k, :].T @ diag(S[:k])

    Key difference from standard PCA:
    - Scale voter projections by sqrt(n_noticias / n_votes_cast)
      This pushes sparse voters away from the center (Polis approach)
    - Scale noticia projections by sqrt(n_voters / n_votes_received)
      Same logic for noticias with few votes

    Args:
        vote_matrix: scipy.sparse matrix (N_voters x N_noticias)
                     Values: +1 (buena), 0 (neutral), -1 (mala), NULL (sparse)
        n_components: int, number of components (default 2 for visualization)

    Returns:
        dict with keys:
            - voter_projections: numpy array (N_voters x n_components)
            - noticia_projections: numpy array (N_noticias x n_components)
            - variance_explained: array of variance ratios
            - voter_vote_counts: votes cast per voter
            - noticia_vote_counts: votes received per noticia
            - singular_values: S from SVD
    """
    n_voters, n_noticias = vote_matrix.shape

    if n_voters < n_components:
        raise ValueError(
            f"Need at least {n_components} voters, got {n_voters}"
        )

    logger.info(
        f"Computing SVD biplot: {n_voters} voters, {n_noticias} noticias, "
        f"{n_components} components"
    )

    # Epsilon value used for neutral votes in sparse matrix (see matrix_builder.py)
    NEUTRAL_EPSILON = 0.0001
    
    # Convert to dense for SVD
    if issparse(vote_matrix):
        vote_matrix_dense = vote_matrix.toarray()
    else:
        vote_matrix_dense = np.array(vote_matrix)
    
    # Convert epsilon back to 0 for neutral votes (for proper mean-centering)
    vote_matrix_dense = np.where(
        np.abs(vote_matrix_dense - NEUTRAL_EPSILON) < 1e-6, 
        0.0, 
        vote_matrix_dense
    )

    # Count votes per voter/noticia (count entries present in sparse matrix)
    if issparse(vote_matrix):
        vote_matrix_for_counting = vote_matrix.toarray()
        # Count non-zero entries OR epsilon (before conversion)
        voter_vote_counts = np.array([
            np.sum((np.abs(vote_matrix_for_counting[i, :]) > 1e-10) | 
                   (np.abs(vote_matrix_for_counting[i, :] - NEUTRAL_EPSILON) < 1e-6))
            for i in range(n_voters)
        ])
        noticia_vote_counts = np.array([
            np.sum((np.abs(vote_matrix_for_counting[:, j]) > 1e-10) | 
                   (np.abs(vote_matrix_for_counting[:, j] - NEUTRAL_EPSILON) < 1e-6))
            for j in range(n_noticias)
        ])
    else:
        voter_vote_counts = np.array([
            np.count_nonzero(vote_matrix_dense[i, :])
            for i in range(n_voters)
        ])
        noticia_vote_counts = np.array([
            np.count_nonzero(vote_matrix_dense[:, j])
            for j in range(n_noticias)
        ])
    
    voter_vote_counts = np.maximum(voter_vote_counts, 1)
    noticia_vote_counts = np.maximum(noticia_vote_counts, 1)

    # Mean-center the matrix (standard PCA preprocessing)
    # Use the converted matrix where epsilon -> 0
    matrix_centered = vote_matrix_dense - vote_matrix_dense.mean(axis=0)

    # SVD decomposition: V = U @ S @ Vt
    U, S, Vt = svd(matrix_centered, full_matrices=False)

    # Compute variance explained
    total_variance = np.sum(S ** 2)
    variance_explained = (S[:n_components] ** 2) / total_variance

    # Extract top k components
    S_k = S[:n_components]

    # Voter projections: U[:, :k] @ diag(S[:k])
    voter_projections = U[:, :n_components] @ np.diag(S_k)

    # Noticia projections: Vt[:k, :].T @ diag(S[:k])
    # This places noticias in the same space as voters
    noticia_projections = Vt[:n_components, :].T @ np.diag(S_k)

    # Sparsity-aware scaling for voters (Polis approach)
    voter_scaling = np.sqrt(n_noticias / voter_vote_counts)
    voter_projections_scaled = voter_projections * voter_scaling[:, np.newaxis]

    # Sparsity-aware scaling for noticias (same logic)
    noticia_scaling = np.sqrt(n_voters / noticia_vote_counts)
    noticia_projections_scaled = (
        noticia_projections * noticia_scaling[:, np.newaxis]
    )

    logger.info(
        f"SVD complete: variance explained = {variance_explained}"
    )
    logger.debug(
        f"Voter projection range: "
        f"x=[{voter_projections_scaled[:, 0].min():.2f}, "
        f"{voter_projections_scaled[:, 0].max():.2f}], "
        f"y=[{voter_projections_scaled[:, 1].min():.2f}, "
        f"{voter_projections_scaled[:, 1].max():.2f}]"
    )
    logger.debug(
        f"Noticia projection range: "
        f"x=[{noticia_projections_scaled[:, 0].min():.2f}, "
        f"{noticia_projections_scaled[:, 0].max():.2f}], "
        f"y=[{noticia_projections_scaled[:, 1].min():.2f}, "
        f"{noticia_projections_scaled[:, 1].max():.2f}]"
    )

    return {
        'voter_projections': voter_projections_scaled,
        'noticia_projections': noticia_projections_scaled,
        'variance_explained': variance_explained,
        'voter_vote_counts': voter_vote_counts,
        'noticia_vote_counts': noticia_vote_counts,
        'singular_values': S,
    }
