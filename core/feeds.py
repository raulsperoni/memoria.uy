"""
Timeline feed algorithms: recientes, confort (afín), puente.

Each function is pure and testable: it receives data (queryset, lookup_data, etc.)
and returns filtered queryset or noticia IDs. No request object dependency.
"""

import logging
from typing import Optional

from django.db.models import Q, QuerySet

logger = logging.getLogger(__name__)

# Feed mode names (used in URLs and view logic)
FEED_RECIENTES = "recientes"
FEED_CONFORT = "confort"
FEED_PUENTE = "puente"
FEED_AVANZADO = "avanzado"
DEFAULT_FEED = FEED_RECIENTES

# Consensus threshold for "cluster rates positively" in comfort feed
COMFORT_CLUSTER_CONSENSUS_MIN = 0.6

# Consensus threshold for cross-cluster agreement in bridge feed
PUENTE_CONSENSUS_THRESHOLD = 0.7
PUENTE_MIN_VOTES_PER_CLUSTER = 3
PUENTE_TOP_N = 500


def filter_recientes(queryset: QuerySet, *, user=None, session_key: Optional[str] = None) -> QuerySet:
    """
    Recientes feed: unvoted noticias, chronological (no personalization).

    Args:
        queryset: Base Noticia queryset (e.g. Noticia.objects.all()).
        user: Authenticated user or None.
        session_key: Session key for anonymous voter or None.

    Returns:
        Queryset with voted noticias excluded (same ordering as input).
    """
    from core.models import Voto

    if user is not None:
        return queryset.exclude(votos__usuario=user)
    if session_key:
        return queryset.exclude(votos__session_key=session_key)
    return queryset


def get_confort_noticia_ids(
    voter_type: str,
    voter_id: str,
    lookup_data: dict,
    *,
    cluster_consensus_min: float = COMFORT_CLUSTER_CONSENSUS_MIN,
) -> Optional[set]:
    """
    Comfort (afín) feed: noticia IDs that align with the voter.

    Combines:
    1) Noticias the voter's cluster rates positively (consensus "buena" >= threshold).
    2) Noticias that other members of the same cluster voted "buena" on (people like you).
    3) Noticias about entities the voter has engaged with positively.

    Args:
        voter_type: "user" or "session".
        voter_id: User PK as string, or session key.
        lookup_data: Dict to filter Voto (e.g. {"usuario": user} or {"session_key": sk}).
        cluster_consensus_min: Minimum cluster consensus for "buena" (default 0.6).

    Returns:
        Set of noticia IDs, or None if no cluster membership (caller should fall back to recientes).
    """
    from core.models import (
        VoterClusterRun,
        VoterClusterMembership,
        ClusterVotingPattern,
        Voto,
        NoticiaEntidad,
    )

    if not voter_id:
        return None

    cluster_run = (
        VoterClusterRun.objects.filter(status="completed")
        .order_by("-created_at")
        .first()
    )
    if not cluster_run:
        return None

    membership = VoterClusterMembership.objects.filter(
        cluster__run=cluster_run,
        cluster__cluster_type="group",
        voter_type=voter_type,
        voter_id=voter_id,
    ).select_related("cluster").first()
    if not membership:
        membership = VoterClusterMembership.objects.filter(
            cluster__run=cluster_run,
            cluster__cluster_type="base",
            voter_type=voter_type,
            voter_id=voter_id,
        ).select_related("cluster").first()
    if not membership:
        return None

    comfort_ids = set()

    # 1) Cluster rates positively (consensus "buena" >= threshold)
    cluster_positive = ClusterVotingPattern.objects.filter(
        cluster=membership.cluster,
        majority_opinion="buena",
        consensus_score__gte=cluster_consensus_min,
    ).values_list("noticia_id", flat=True)
    comfort_ids.update(cluster_positive)

    # 2) "People who vote like you also liked these" — other cluster members voted "buena"
    other_members = list(
        membership.cluster.members.exclude(
            voter_type=voter_type, voter_id=voter_id
        ).values_list("voter_type", "voter_id")
    )
    if other_members:
        user_ids = []
        for m in other_members:
            if m[0] == "user":
                try:
                    user_ids.append(int(m[1]))
                except (ValueError, TypeError):
                    pass
        session_keys = [m[1] for m in other_members if m[0] == "session"]
        if user_ids or session_keys:
            q = Q(opinion="buena")
            if user_ids and session_keys:
                q &= Q(usuario_id__in=user_ids) | Q(session_key__in=session_keys)
            elif user_ids:
                q &= Q(usuario_id__in=user_ids)
            else:
                q &= Q(session_key__in=session_keys)
            cluster_peers_buena = (
                Voto.objects.filter(q).values_list("noticia_id", flat=True).distinct()
            )
            comfort_ids.update(cluster_peers_buena)

    # 3) Noticias about entities they've engaged with positively
    my_buena_votes = Voto.objects.filter(
        **lookup_data, opinion="buena"
    ).values_list("noticia_id", flat=True)
    if my_buena_votes:
        liked_entity_ids = set(
            NoticiaEntidad.objects.filter(
                noticia_id__in=my_buena_votes,
                sentimiento="positivo",
            ).values_list("entidad_id", flat=True)
        )
        if liked_entity_ids:
            noticias_about_liked = NoticiaEntidad.objects.filter(
                entidad_id__in=liked_entity_ids,
                sentimiento="positivo",
            ).values_list("noticia_id", flat=True)
            comfort_ids.update(noticias_about_liked)

    return comfort_ids if comfort_ids else None


def get_puente_ordered_noticia_ids(
    lookup_data: dict,
    *,
    consensus_threshold: float = PUENTE_CONSENSUS_THRESHOLD,
    min_votes_per_cluster: int = PUENTE_MIN_VOTES_PER_CLUSTER,
    top_n: int = PUENTE_TOP_N,
) -> list:
    """
    Puente feed: noticia IDs in consensus order, excluding already voted by this voter.

    Uses cross-cluster consensus (noticias where many burbujas agree). Excludes
    noticias the voter has already voted on.

    Args:
        lookup_data: Dict to filter Voto for current voter (e.g. {"usuario": user}).
        consensus_threshold: Min agreement rate across clusters (default 0.7).
        min_votes_per_cluster: Min votes per cluster to consider (default 3).
        top_n: Max number of consensus noticias to consider (default 500).

    Returns:
        List of noticia IDs in consensus order (highest agreement first), excluding voted.
        Empty list if no cluster run or no consensus data.
    """
    from core.clustering.consensus import calculate_consensus_news
    from core.models import VoterClusterRun, Voto

    cluster_run = (
        VoterClusterRun.objects.filter(status="completed")
        .order_by("-created_at")
        .first()
    )
    if not cluster_run:
        return []

    consensus_list = calculate_consensus_news(
        cluster_run,
        min_votes_per_cluster=min_votes_per_cluster,
        consensus_threshold=consensus_threshold,
        top_n=top_n,
    )
    if not consensus_list:
        return []

    ordered_ids = [r["noticia_id"] for r in consensus_list]

    # Exclude already voted
    voted = set(
        Voto.objects.filter(**lookup_data).values_list("noticia_id", flat=True)
    )
    ordered_ids = [nid for nid in ordered_ids if nid not in voted]
    return ordered_ids
