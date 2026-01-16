"""
API endpoints for voter clustering (Polis-style).

Provides clustering data for visualization and analysis.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.core.cache import cache
from django.db.models import Prefetch
from core.models import (
    VoterClusterRun,
    VoterCluster,
    VoterProjection,
    VoterClusterMembership,
    ClusterVotingPattern,
)
from core.views import get_voter_identifier
from core.tasks import update_voter_clusters
import logging

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([AllowAny])
def cluster_data(request):
    """
    GET /api/clustering/data/

    Returns full clustering results (Polis-compatible format).

    Query parameters:
        run_id (optional): Specific run ID (default: latest completed)

    Response:
        {
            "cluster_run_id": int,
            "n_voters": int,
            "n_noticias": int,
            "last_updated": str (ISO datetime),
            "pca": {
                "variance_explained": [float, float],
                "n_components": 2
            },
            "projections": [
                {
                    "voter_id": str,
                    "voter_type": str,
                    "x": float,
                    "y": float,
                    "n_votes": int
                },
                ...
            ],
            "base_clusters": [
                {
                    "id": int,
                    "size": int,
                    "centroid": [float, float],
                    "consensus_score": float
                },
                ...
            ],
            "group_clusters": [...],
            "parameters": {...}
        }
    """
    run_id = request.GET.get('run_id')

    if run_id:
        try:
            run = VoterClusterRun.objects.get(id=run_id, status='completed')
        except VoterClusterRun.DoesNotExist:
            return Response(
                {'error': f'No completed run with id {run_id}'},
                status=404
            )
    else:
        # Get latest successful run
        run = VoterClusterRun.objects.filter(
            status='completed'
        ).order_by('-created_at').first()

        if not run:
            return Response(
                {'error': 'No clustering data available'},
                status=404
            )

    # Check cache
    cache_key = f'cluster_data_{run.id}'
    cached = cache.get(cache_key)
    if cached:
        logger.debug(f"Returning cached cluster data for run {run.id}")
        return Response(cached)

    # Build response
    logger.info(f"Building cluster data response for run {run.id}")

    # Get projections
    projections = run.projections.all()
    projections_data = [
        {
            'voter_id': p.voter_id,
            'voter_type': p.voter_type,
            'x': p.projection_x,
            'y': p.projection_y,
            'n_votes': p.n_votes_cast
        }
        for p in projections
    ]

    # Get base clusters
    base_clusters = run.clusters.filter(cluster_type='base')
    base_clusters_data = [
        {
            'id': c.cluster_id,
            'size': c.size,
            'centroid': [c.centroid_x, c.centroid_y],
            'consensus_score': c.consensus_score
        }
        for c in base_clusters
    ]

    # Get group clusters
    group_clusters = run.clusters.filter(cluster_type='group')
    group_clusters_data = [
        {
            'id': c.cluster_id,
            'size': c.size,
            'centroid': [c.centroid_x, c.centroid_y],
            'consensus_score': c.consensus_score,
            'name': c.llm_name,
            'description': c.llm_description,
            'entities_positive': c.top_entities_positive or [],
            'entities_negative': c.top_entities_negative or [],
        }
        for c in group_clusters
    ]

    data = {
        'cluster_run_id': run.id,
        'n_voters': run.n_voters,
        'n_noticias': run.n_noticias,
        'last_updated': run.completed_at.isoformat() if run.completed_at else None,
        'pca': {
            'variance_explained': run.parameters.get('variance_explained', []),
            'n_components': 2
        },
        'projections': projections_data,
        'base_clusters': base_clusters_data,
        'group_clusters': group_clusters_data,
        'parameters': run.parameters,
        'status': run.status,
        'computation_time': run.computation_time
    }

    # Cache for 1 hour
    cache.set(cache_key, data, 3600)

    return Response(data)


@api_view(['GET'])
@permission_classes([AllowAny])
def voter_cluster_membership(request):
    """
    GET /api/clustering/voter/me/

    Returns current voter's cluster membership and projection.

    Response:
        {
            "voter_id": str,
            "voter_type": str,
            "cluster_id": int,
            "cluster_size": int,
            "cluster_consensus": float,
            "projection": {"x": float, "y": float},
            "n_votes_cast": int,
            "distance_to_centroid": float
        }
    """
    voter_info = get_voter_identifier(request)

    # Get latest run
    run = VoterClusterRun.objects.filter(
        status='completed'
    ).order_by('-created_at').first()

    if not run:
        return Response(
            {'error': 'No clustering data available'},
            status=404
        )

    # Determine voter type and ID
    if 'usuario' in voter_info and voter_info['usuario']:
        voter_type = 'user'
        voter_id = str(voter_info['usuario'])
    elif 'session_key' in voter_info:
        voter_type = 'session'
        voter_id = voter_info['session_key']
    else:
        return Response(
            {'error': 'Could not identify voter'},
            status=400
        )

    # Find voter's projection
    try:
        projection = run.projections.get(
            voter_type=voter_type,
            voter_id=voter_id
        )
    except VoterProjection.DoesNotExist:
        return Response(
            {'error': 'Voter not found in clustering'},
            status=404
        )

    # Find voter's cluster membership (base cluster)
    membership = VoterClusterMembership.objects.filter(
        cluster__run=run,
        cluster__cluster_type='base',
        voter_type=voter_type,
        voter_id=voter_id
    ).select_related('cluster').first()

    if not membership:
        return Response(
            {
                'voter_id': voter_id,
                'voter_type': voter_type,
                'projection': {
                    'x': projection.projection_x,
                    'y': projection.projection_y
                },
                'n_votes_cast': projection.n_votes_cast,
                'cluster_id': None,
                'message': 'No cluster assignment found'
            }
        )

    return Response({
        'voter_id': voter_id,
        'voter_type': voter_type,
        'cluster_id': membership.cluster.cluster_id,
        'cluster_size': membership.cluster.size,
        'cluster_consensus': membership.cluster.consensus_score,
        'projection': {
            'x': projection.projection_x,
            'y': projection.projection_y
        },
        'n_votes_cast': projection.n_votes_cast,
        'distance_to_centroid': membership.distance_to_centroid
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def cluster_voting_patterns(request, cluster_id):
    """
    GET /api/clustering/clusters/<cluster_id>/votes/

    Returns voting patterns for a specific cluster.

    Response:
        {
            "cluster_id": int,
            "cluster_size": int,
            "consensus_score": float,
            "voting_patterns": [
                {
                    "noticia_id": int,
                    "buena": int,
                    "mala": int,
                    "neutral": int,
                    "total": int,
                    "majority_opinion": str,
                    "consensus": float
                },
                ...
            ]
        }
    """
    # Get latest run
    run = VoterClusterRun.objects.filter(
        status='completed'
    ).order_by('-created_at').first()

    if not run:
        return Response(
            {'error': 'No clustering data available'},
            status=404
        )

    # Find cluster
    try:
        cluster = run.clusters.get(
            cluster_id=cluster_id,
            cluster_type='base'
        )
    except VoterCluster.DoesNotExist:
        return Response(
            {'error': f'Cluster {cluster_id} not found'},
            status=404
        )

    # Get voting patterns
    patterns = cluster.voting_patterns.all()

    voting_patterns_data = [
        {
            'noticia_id': p.noticia_id,
            'buena': p.count_buena,
            'mala': p.count_mala,
            'neutral': p.count_neutral,
            'total': p.count_buena + p.count_mala + p.count_neutral,
            'majority_opinion': p.majority_opinion,
            'consensus': p.consensus_score
        }
        for p in patterns
    ]

    return Response({
        'cluster_id': cluster.cluster_id,
        'cluster_size': cluster.size,
        'consensus_score': cluster.consensus_score,
        'voting_patterns': voting_patterns_data
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def trigger_clustering(request):
    """
    POST /api/clustering/trigger/

    Manually trigger clustering computation (async).

    Request body (optional):
        {
            "time_window_days": int,
            "min_voters": int,
            "min_votes_per_voter": int
        }

    Response:
        {
            "task_id": str,
            "message": str
        }
    """
    time_window_days = request.data.get('time_window_days', 30)
    min_voters = request.data.get('min_voters', 50)
    min_votes_per_voter = request.data.get('min_votes_per_voter', 3)

    logger.info(
        f"Triggering clustering: days={time_window_days}, "
        f"min_voters={min_voters}"
    )

    result = update_voter_clusters.delay(
        time_window_days=time_window_days,
        min_voters=min_voters,
        min_votes_per_voter=min_votes_per_voter
    )

    return Response({
        'task_id': result.id,
        'message': 'Clustering task dispatched',
        'parameters': {
            'time_window_days': time_window_days,
            'min_voters': min_voters,
            'min_votes_per_voter': min_votes_per_voter
        }
    })
