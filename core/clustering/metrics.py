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
from scipy.sparse import issparse
from sklearn.metrics import silhouette_score
import logging

logger = logging.getLogger(__name__)


def compute_cluster_consensus(cluster_votes):
    """
    Measure within-cluster agreement on voting.

    Consensus score: How much does the cluster agree on each article?
    Higher score = stronger agreement.

    Args:
        cluster_votes: dict {noticia_id: {'buena': count, 'mala': count, 'neutral': count}}

    Returns:
        float: consensus score (0-1)
            0 = complete disagreement
            1 = complete agreement
    """
    if not cluster_votes:
        return 0.0

    consensus_scores = []

    for noticia_id, vote_counts in cluster_votes.items():
        total = sum(vote_counts.values())
        if total == 0:
            continue

        # Consensus = (max_count / total)
        # When everyone agrees, max_count = total, consensus = 1
        max_count = max(vote_counts.values())
        consensus = max_count / total
        consensus_scores.append(consensus)

    if not consensus_scores:
        return 0.0

    # Average consensus across all articles
    return np.mean(consensus_scores)


def compute_voter_similarity(voter_a_votes, voter_b_votes):
    """
    Pairwise similarity between two voters.

    Similarity = (number of agreements) / (number of co-voted articles)

    Args:
        voter_a_votes: dict {noticia_id: opinion}
        voter_b_votes: dict {noticia_id: opinion}

    Returns:
        float: similarity (0-1)
            0 = complete disagreement
            1 = complete agreement
            None = no co-voted articles
    """
    # Find co-voted articles
    co_voted = set(voter_a_votes.keys()) & set(voter_b_votes.keys())

    if not co_voted:
        return None

    # Count agreements
    agreements = sum(
        1 for nid in co_voted
        if voter_a_votes[nid] == voter_b_votes[nid]
    )

    similarity = agreements / len(co_voted)
    return similarity


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


def compute_cluster_voting_aggregation(
    cluster_members,
    voter_ids_list,
    vote_matrix,
    noticia_ids_list
):
    """
    Aggregate voting patterns for a cluster.

    Args:
        cluster_members: array of voter indices in this cluster
        voter_ids_list: list of (voter_type, voter_id) tuples
        vote_matrix: sparse matrix (N_voters × N_noticias)
        noticia_ids_list: list of noticia IDs

    Returns:
        dict: {
            noticia_id: {
                'buena': count,
                'mala': count,
                'neutral': count,
                'total': count
            }
        }
    """
    aggregation = {}

    if issparse(vote_matrix):
        vote_matrix_dense = vote_matrix.toarray()
    else:
        vote_matrix_dense = vote_matrix

    for noticia_idx, noticia_id in enumerate(noticia_ids_list):
        # Get votes from cluster members for this noticia
        votes_on_noticia = vote_matrix_dense[cluster_members, noticia_idx]

        # Count by opinion
        buena_count = np.sum(votes_on_noticia == 1)
        mala_count = np.sum(votes_on_noticia == -1)
        neutral_count = np.sum(votes_on_noticia == 0)

        total = buena_count + mala_count + neutral_count

        if total > 0:
            aggregation[noticia_id] = {
                'buena': int(buena_count),
                'mala': int(mala_count),
                'neutral': int(neutral_count),
                'total': int(total)
            }

    return aggregation


def compute_distance_to_centroid(projection, centroid):
    """
    Compute Euclidean distance from voter to cluster centroid.

    Args:
        projection: numpy array (2,), voter's 2D coordinates
        centroid: numpy array (2,), cluster center

    Returns:
        float: distance
    """
    return np.linalg.norm(projection - centroid)


def compute_cluster_entities(cluster, top_n=5):
    """
    Extract top entities viewed positively/negatively by a cluster.

    Analyzes the noticias where the cluster has strong consensus and
    aggregates their associated entities by sentiment.

    Args:
        cluster: VoterCluster instance with voting_patterns
        top_n: number of entities to return per sentiment

    Returns:
        tuple: (entities_positive, entities_negative)
            Each is a list of dicts: [{"nombre": str, "tipo": str, "count": int}]
    """
    from collections import Counter
    from core.models import NoticiaEntidad

    # Get noticias where cluster voted with consensus
    patterns = cluster.voting_patterns.filter(
        consensus_score__gte=0.6
    ).select_related('noticia')

    # Separate by majority opinion
    noticias_buena = [p.noticia_id for p in patterns if p.majority_opinion == 'buena']
    noticias_mala = [p.noticia_id for p in patterns if p.majority_opinion == 'mala']

    # For noticias voted "buena": entities with positive sentiment are "liked"
    # For noticias voted "mala": entities with negative sentiment are "disliked"
    entities_positive = Counter()
    entities_negative = Counter()

    # Entities from positively-voted noticias
    if noticias_buena:
        positive_nes = NoticiaEntidad.objects.filter(
            noticia_id__in=noticias_buena,
            sentimiento='positivo'
        ).select_related('entidad')
        for ne in positive_nes:
            key = (ne.entidad.nombre, ne.entidad.tipo)
            entities_positive[key] += 1

    # Entities from negatively-voted noticias
    if noticias_mala:
        negative_nes = NoticiaEntidad.objects.filter(
            noticia_id__in=noticias_mala,
            sentimiento='negativo'
        ).select_related('entidad')
        for ne in negative_nes:
            key = (ne.entidad.nombre, ne.entidad.tipo)
            entities_negative[key] += 1

    # Format results
    top_positive = [
        {"nombre": nombre, "tipo": tipo, "count": count}
        for (nombre, tipo), count in entities_positive.most_common(top_n)
    ]
    top_negative = [
        {"nombre": nombre, "tipo": tipo, "count": count}
        for (nombre, tipo), count in entities_negative.most_common(top_n)
    ]

    return top_positive, top_negative
