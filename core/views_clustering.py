"""
Views for cluster visualization and analysis.
"""

from django.views.generic import TemplateView
from django.http import JsonResponse
from core.models import VoterClusterRun
from core.views import get_voter_identifier
import logging

logger = logging.getLogger(__name__)


class ClusterVisualizationView(TemplateView):
    """
    Interactive cluster visualization page.

    Shows 2D scatter plot of voter clusters with interactive features:
    - Hover to see voter details
    - Click cluster to filter timeline
    - Color-coded by cluster
    - Convex hulls showing cluster boundaries
    """
    template_name = 'clustering/visualization.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get latest clustering run
        run = VoterClusterRun.objects.filter(
            status='completed'
        ).order_by('-created_at').first()

        if run:
            context['cluster_run'] = run
            context['has_clustering'] = True

            # Get current voter's info
            voter_info = get_voter_identifier(self.request)
            if 'usuario' in voter_info and voter_info['usuario']:
                context['voter_type'] = 'user'
                context['voter_id'] = str(voter_info['usuario'])
            elif 'session_key' in voter_info:
                context['voter_type'] = 'session'
                context['voter_id'] = voter_info['session_key']

            # Add statistics
            context['n_voters'] = run.n_voters
            context['n_clusters'] = run.n_clusters
            context['n_noticias'] = run.n_noticias
            context['silhouette_score'] = run.parameters.get(
                'silhouette_score',
                0
            )
            context['variance_explained'] = run.parameters.get(
                'variance_explained',
                []
            )
        else:
            context['has_clustering'] = False
            context['message'] = (
                'No hay datos de clustering disponibles. '
                'Se necesitan al menos 50 votantes con 3 votos cada uno.'
            )

        return context


class ClusterStatsView(TemplateView):
    """
    Cluster statistics and analytics page.

    Shows:
    - Cluster sizes and consensus scores
    - Top voted noticias per cluster
    - Polarization metrics
    - Temporal trends (if available)
    """
    template_name = 'clustering/stats.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get latest run
        run = VoterClusterRun.objects.filter(
            status='completed'
        ).order_by('-created_at').first()

        if run:
            # Get all clusters with voting patterns
            clusters = run.clusters.filter(
                cluster_type='base'
            ).prefetch_related('voting_patterns').order_by('cluster_id')

            cluster_stats = []
            for cluster in clusters:
                # Calculate top noticias
                patterns = cluster.voting_patterns.order_by(
                    '-consensus_score'
                )[:5]

                cluster_stats.append({
                    'cluster': cluster,
                    'top_patterns': patterns,
                    'avg_consensus': cluster.consensus_score or 0,
                })

            context['cluster_stats'] = cluster_stats
            context['cluster_run'] = run
            context['has_data'] = True
        else:
            context['has_data'] = False

        return context


def cluster_data_json(request):
    """
    JSON endpoint for cluster data (for JavaScript visualization).

    Returns lightweight JSON suitable for D3.js/Plotly.js:
    - Projections with cluster assignments
    - Cluster centroids
    - Current voter highlight
    """
    run_id = request.GET.get('run_id')

    if run_id:
        try:
            run = VoterClusterRun.objects.get(
                id=run_id,
                status='completed'
            )
        except VoterClusterRun.DoesNotExist:
            return JsonResponse({'error': 'Run not found'}, status=404)
    else:
        run = VoterClusterRun.objects.filter(
            status='completed'
        ).order_by('-created_at').first()

    if not run:
        return JsonResponse(
            {'error': 'No clustering data available'},
            status=404
        )

    # Get voter identifier
    voter_info = get_voter_identifier(request)
    current_voter_type = None
    current_voter_id = None

    if 'usuario' in voter_info and voter_info['usuario']:
        current_voter_type = 'user'
        current_voter_id = str(voter_info['usuario'])
    elif 'session_key' in voter_info:
        current_voter_type = 'session'
        current_voter_id = voter_info['session_key']

    # Build projections with cluster assignments
    projections = []
    memberships = {}

    # Get all memberships
    for membership in run.clusters.filter(
        cluster_type='base'
    ).prefetch_related('members'):
        for member in membership.members.all():
            key = f"{member.voter_type}:{member.voter_id}"
            memberships[key] = {
                'cluster_id': membership.cluster_id,
                'cluster_size': membership.size,
                'distance': member.distance_to_centroid,
            }

    # Get projections
    for proj in run.projections.all():
        key = f"{proj.voter_type}:{proj.voter_id}"
        cluster_info = memberships.get(key, {})

        is_current = (
            proj.voter_type == current_voter_type and
            proj.voter_id == current_voter_id
        )

        projections.append({
            'x': proj.projection_x,
            'y': proj.projection_y,
            'voter_type': proj.voter_type,
            'voter_id': proj.voter_id,
            'n_votes': proj.n_votes_cast,
            'cluster_id': cluster_info.get('cluster_id'),
            'cluster_size': cluster_info.get('cluster_size'),
            'is_current_voter': is_current,
        })

    # Get cluster centroids
    centroids = []
    for cluster in run.clusters.filter(cluster_type='base'):
        centroids.append({
            'cluster_id': cluster.cluster_id,
            'x': cluster.centroid_x,
            'y': cluster.centroid_y,
            'size': cluster.size,
            'consensus': cluster.consensus_score,
        })

    return JsonResponse({
        'run_id': run.id,
        'n_voters': run.n_voters,
        'n_clusters': run.n_clusters,
        'projections': projections,
        'centroids': centroids,
        'current_voter': {
            'type': current_voter_type,
            'id': current_voter_id,
        } if current_voter_type else None,
        'variance_explained': run.parameters.get('variance_explained', []),
    })
