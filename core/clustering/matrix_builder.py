"""
Vote matrix builder for clustering analysis.

Converts vote records from the database into a sparse matrix
suitable for PCA and clustering operations.
"""

from scipy.sparse import lil_matrix
import numpy as np
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q
import logging

logger = logging.getLogger(__name__)


def build_vote_matrix(time_window_days=30, min_votes_per_voter=3):
    """
    Build sparse vote matrix (voters × noticias) from database.

    Args:
        time_window_days: Only include votes from last N days
        min_votes_per_voter: Minimum votes to include a voter

    Returns:
        tuple: (vote_matrix, voter_ids, noticia_ids)
            - vote_matrix: scipy.sparse.lil_matrix (N_voters × N_noticias)
            - voter_ids: list of (voter_type, voter_id) tuples
            - noticia_ids: list of noticia primary keys

    Encoding:
        buena = +1
        neutral = 0
        mala = -1
        no_vote = NULL (sparse)
    """
    from core.models import Voto, Noticia

    # Calculate cutoff date
    cutoff_date = timezone.now() - timedelta(days=time_window_days)

    # Fetch votes within time window
    votes = Voto.objects.filter(
        fecha_voto__gte=cutoff_date
    ).select_related('noticia').values(
        'usuario_id',
        'session_key',
        'noticia_id',
        'opinion'
    )

    if not votes.exists():
        logger.warning("No votes found in time window")
        return lil_matrix((0, 0)), [], []

    # Build voter identifier mapping
    voter_id_map = {}
    voter_vote_counts = {}
    voter_ids_list = []

    for vote in votes:
        if vote['usuario_id']:
            voter_key = ('user', str(vote['usuario_id']))
        elif vote['session_key']:
            voter_key = ('session', vote['session_key'])
        else:
            continue  # Skip invalid votes

        # Count votes per voter
        if voter_key not in voter_vote_counts:
            voter_vote_counts[voter_key] = 0
        voter_vote_counts[voter_key] += 1

    # Filter voters by minimum vote threshold
    qualified_voters = {
        voter_key
        for voter_key, count in voter_vote_counts.items()
        if count >= min_votes_per_voter
    }

    logger.info(
        f"Found {len(voter_vote_counts)} voters, "
        f"{len(qualified_voters)} meet minimum {min_votes_per_voter} votes"
    )

    if not qualified_voters:
        logger.warning(
            f"No voters with at least {min_votes_per_voter} votes"
        )
        return lil_matrix((0, 0)), [], []

    # Assign indices to qualified voters
    for i, voter_key in enumerate(sorted(qualified_voters)):
        voter_id_map[voter_key] = i
        voter_ids_list.append(voter_key)

    # Build noticia index mapping
    noticia_ids_set = {
        vote['noticia_id']
        for vote in votes
        if (
            (vote['usuario_id'] and ('user', str(vote['usuario_id'])) in qualified_voters) or
            (vote['session_key'] and ('session', vote['session_key']) in qualified_voters)
        )
    }
    noticia_ids_list = sorted(noticia_ids_set)
    noticia_id_map = {nid: i for i, nid in enumerate(noticia_ids_list)}

    # Initialize sparse matrix
    n_voters = len(voter_ids_list)
    n_noticias = len(noticia_ids_list)
    vote_matrix = lil_matrix((n_voters, n_noticias), dtype=np.float32)

    # Opinion encoding: Use epsilon for neutral so it's stored in sparse matrix
    # (scipy sparse doesn't store 0s, so we use 0.0001 and convert back to 0.0 later)
    NEUTRAL_EPSILON = 0.0001
    opinion_encoding = {
        'buena': 1.0,
        'neutral': NEUTRAL_EPSILON,
        'mala': -1.0,
    }

    # Fill matrix
    for vote in votes:
        # Get voter key
        if vote['usuario_id']:
            voter_key = ('user', str(vote['usuario_id']))
        elif vote['session_key']:
            voter_key = ('session', vote['session_key'])
        else:
            continue

        # Skip if voter not qualified
        if voter_key not in voter_id_map:
            continue

        # Skip if noticia not in our set
        if vote['noticia_id'] not in noticia_id_map:
            continue

        voter_idx = voter_id_map[voter_key]
        noticia_idx = noticia_id_map[vote['noticia_id']]
        opinion_value = opinion_encoding.get(vote['opinion'], NEUTRAL_EPSILON)

        vote_matrix[voter_idx, noticia_idx] = opinion_value

    # Log statistics
    density = vote_matrix.nnz / (n_voters * n_noticias) * 100
    logger.info(
        f"Built vote matrix: {n_voters} voters × {n_noticias} noticias "
        f"({vote_matrix.nnz} non-zero votes, {density:.1f}% density)"
    )

    return vote_matrix, voter_ids_list, noticia_ids_list
