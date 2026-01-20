"""
Views for cluster visualization and analysis.
"""

from django.views.generic import TemplateView
from django.http import JsonResponse, HttpResponse
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from django.contrib.auth import get_user_model
from core.models import VoterClusterRun, Voto, Noticia
from core.views import get_voter_identifier
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
from urllib.parse import urlparse
import logging
import os

User = get_user_model()

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
            voter_info, _ = get_voter_identifier(self.request)
            voter_type = None
            voter_id = None
            
            if 'usuario' in voter_info and voter_info['usuario']:
                voter_type = 'user'
                voter_id = str(voter_info['usuario'].id)
                context['voter_type'] = voter_type
                context['voter_id'] = voter_id
            elif 'session_key' in voter_info:
                voter_type = 'session'
                voter_id = voter_info['session_key']
                context['voter_type'] = voter_type
                context['voter_id'] = voter_id

            # Check if URL has a specific cluster parameter (for shared links)
            shared_cluster_id = self.request.GET.get('cluster')
            
            if shared_cluster_id is not None:
                logger.info(f"[Cluster Context] Shared link detected - cluster={shared_cluster_id}")
                try:
                    shared_cluster = run.clusters.filter(
                        cluster_type='group',
                        cluster_id=int(shared_cluster_id)
                    ).first()
                    
                    if shared_cluster:
                        context['user_cluster_name'] = shared_cluster.llm_name or f"Burbuja {shared_cluster.cluster_id}"
                        context['user_cluster_description'] = shared_cluster.llm_description or ''
                        context['user_cluster_id'] = shared_cluster.cluster_id
                        context['user_cluster_size'] = shared_cluster.size
                        logger.info(f"[Cluster Context] ✓ Using shared cluster: {shared_cluster.cluster_id} ({context['user_cluster_name']})")
                except (ValueError, TypeError) as e:
                    logger.error(f"[Cluster Context] Invalid cluster parameter: {e}")
            
            # Otherwise, get current voter's cluster info for sharing/meta tags
            elif voter_type and voter_id:
                logger.info(f"[Cluster Context] Looking for current voter's cluster - voter_type={voter_type}, voter_id={voter_id[:20] if len(str(voter_id)) > 20 else voter_id}")
                
                membership = run.clusters.filter(
                    cluster_type='group',
                    members__voter_type=voter_type,
                    members__voter_id=voter_id
                ).first()
                
                logger.info(f"[Cluster Context] Membership found: {bool(membership)}")
                
                if membership:
                    context['user_cluster_name'] = membership.llm_name or f"Burbuja {membership.cluster_id}"
                    context['user_cluster_description'] = membership.llm_description or ''
                    context['user_cluster_id'] = membership.cluster_id
                    context['user_cluster_size'] = membership.size
                    logger.info(f"[Cluster Context] ✓ User cluster: {membership.cluster_id} ({context['user_cluster_name']})")
                else:
                    logger.warning(f"[Cluster Context] ⚠️ No cluster found for this voter")

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
            # Get group clusters (not base) with voting patterns
            clusters = run.clusters.filter(
                cluster_type='group'
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

            # Add votes over time statistics
            thirty_days_ago = timezone.now() - timedelta(days=30)
            votes_by_day = Voto.objects.filter(
                fecha_voto__gte=thirty_days_ago
            ).annotate(
                day=TruncDate('fecha_voto')
            ).values('day').annotate(
                count=Count('id')
            ).order_by('day')

            # Also get votes by opinion over time
            votes_by_opinion_day = Voto.objects.filter(
                fecha_voto__gte=thirty_days_ago
            ).annotate(
                day=TruncDate('fecha_voto')
            ).values('day', 'opinion').annotate(
                count=Count('id')
            ).order_by('day', 'opinion')

            # Convert to JSON-serializable format
            import json
            context['votes_by_day'] = json.dumps([
                {'day': v['day'].isoformat(), 'count': v['count']}
                for v in votes_by_day
            ])
            context['votes_by_opinion_day'] = json.dumps([
                {
                    'day': v['day'].isoformat(),
                    'opinion': v['opinion'],
                    'count': v['count']
                }
                for v in votes_by_opinion_day
            ])

            # Calculate total votes
            total_votes = Voto.objects.count()
            votes_last_7_days = Voto.objects.filter(
                fecha_voto__gte=timezone.now() - timedelta(days=7)
            ).count()
            votes_last_30_days = Voto.objects.filter(
                fecha_voto__gte=thirty_days_ago
            ).count()

            context['total_votes'] = total_votes
            context['votes_last_7_days'] = votes_last_7_days
            context['votes_last_30_days'] = votes_last_30_days
        else:
            context['has_data'] = False

        # User and activity statistics (always show, independent of clustering)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        seven_days_ago = timezone.now() - timedelta(days=7)
        
        # User counts
        total_users = User.objects.filter(is_active=True).count()
        users_last_7_days = User.objects.filter(
            date_joined__gte=seven_days_ago
        ).count()
        users_last_30_days = User.objects.filter(
            date_joined__gte=thirty_days_ago
        ).count()
        
        # Users by day (last 30 days)
        users_by_day = User.objects.filter(
            date_joined__gte=thirty_days_ago
        ).annotate(
            day=TruncDate('date_joined')
        ).values('day').annotate(
            count=Count('id')
        ).order_by('day')
        
        # Active users (voted or submitted news in last 30 days)
        active_user_ids = set(
            Voto.objects.filter(
                usuario__isnull=False,
                fecha_voto__gte=thirty_days_ago
            ).values_list('usuario_id', flat=True)
        ) | set(
            Noticia.objects.filter(
                agregado_por__isnull=False,
                fecha_agregado__gte=thirty_days_ago
            ).values_list('agregado_por_id', flat=True)
        )
        active_users_30_days = len(active_user_ids)
        
        # Unique voters (authenticated + anonymous sessions)
        unique_voters_30_days = Voto.objects.filter(
            fecha_voto__gte=thirty_days_ago
        ).values('usuario_id', 'session_key').distinct().count()
        
        # News submissions over time
        news_by_day = Noticia.objects.filter(
            fecha_agregado__gte=thirty_days_ago
        ).annotate(
            day=TruncDate('fecha_agregado')
        ).values('day').annotate(
            count=Count('id')
        ).order_by('day')
        
        import json
        context['users_by_day'] = json.dumps([
            {'day': u['day'].isoformat(), 'count': u['count']}
            for u in users_by_day
        ])
        context['news_by_day'] = json.dumps([
            {'day': n['day'].isoformat(), 'count': n['count']}
            for n in news_by_day
        ])
        
        context['total_users'] = total_users
        context['users_last_7_days'] = users_last_7_days
        context['users_last_30_days'] = users_last_30_days
        context['active_users_30_days'] = active_users_30_days
        context['unique_voters_30_days'] = unique_voters_30_days
        context['total_noticias'] = Noticia.objects.count()

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
    voter_info, _ = get_voter_identifier(request)
    current_voter_type = None
    current_voter_id = None

    if 'usuario' in voter_info and voter_info['usuario']:
        current_voter_type = 'user'
        current_voter_id = str(voter_info['usuario'].id)
        logger.info(f"[Clustering API] Current voter: user {current_voter_id}")
    elif 'session_key' in voter_info:
        current_voter_type = 'session'
        current_voter_id = voter_info['session_key']
        logger.info(f"[Clustering API] Current voter: session {current_voter_id[:20]}...")
    else:
        logger.warning("[Clustering API] No voter identifier found")

    # Build projections with cluster assignments
    projections = []
    memberships = {}

    # Get all memberships (use group clusters for visualization)
    for membership in run.clusters.filter(
        cluster_type='group'
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

    # Get cluster centroids (use group clusters)
    centroids = []
    for cluster in run.clusters.filter(cluster_type='group'):
        centroids.append({
            'cluster_id': cluster.cluster_id,
            'x': cluster.centroid_x,
            'y': cluster.centroid_y,
            'size': cluster.size,
            'consensus': cluster.consensus_score,
            'name': cluster.llm_name,
            'description': cluster.llm_description,
            'entities_positive': cluster.top_entities_positive or [],
            'entities_negative': cluster.top_entities_negative or [],
        })

    # Get noticia projections (biplot)
    news_projections = []
    for np_obj in run.noticia_projections.select_related('noticia').all():
        noticia = np_obj.noticia
        # Extract domain from URL as "medio"
        try:
            domain = urlparse(noticia.enlace).netloc.replace('www.', '')
        except Exception:
            domain = ''
        news_projections.append({
            'id': noticia.id,
            'slug': noticia.slug,
            'x': np_obj.projection_x,
            'y': np_obj.projection_y,
            'n_votes': np_obj.n_votes,
            'titulo': noticia.mostrar_titulo or '',
            'medio': domain,
        })

    return JsonResponse({
        'run_id': run.id,
        'n_voters': run.n_voters,
        'n_clusters': run.n_clusters,
        'n_noticias': run.n_noticias,
        'projections': projections,
        'centroids': centroids,
        'news_projections': news_projections,
        'current_voter': {
            'type': current_voter_type,
            'id': current_voter_id,
        } if current_voter_type else None,
        'variance_explained': run.parameters.get('variance_explained', []),
    })


@require_POST
@csrf_exempt  # Allow from extension/browser without CSRF
def upload_cluster_og_image(request):
    """
    Upload user-captured cluster image to use as OG image.
    
    This is much better than server-side rendering:
    - Real user captures = authentic
    - No need for Playwright/headless browser
    - Free computation (user does it)
    - Always up-to-date
    
    POST body: image blob (JPEG)
    Query params: cluster_id (required)
    """
    logger.info(f"[OG Upload] Received upload request")
    
    try:
        cluster_id = request.GET.get('cluster')
        logger.info(f"[OG Upload] Cluster ID: {cluster_id}")
        
        if not cluster_id:
            logger.warning("[OG Upload] No cluster_id provided")
            return JsonResponse({'error': 'cluster_id required'}, status=400)
        
        # Read image from request body
        image_data = request.body
        image_size = len(image_data)
        logger.info(f"[OG Upload] Image size: {image_size / 1024:.1f} KB")
        
        if not image_data or image_size < 1000:  # Sanity check
            logger.warning(f"[OG Upload] Invalid image data (size: {image_size})")
            return JsonResponse({'error': 'Invalid image data'}, status=400)
        
        # Save image with cluster_id in filename
        filename = f'og-cluster-{cluster_id}.jpg'
        filepath = os.path.join('og-images', filename)
        
        # Delete old version if exists
        if default_storage.exists(filepath):
            default_storage.delete(filepath)
            logger.info(f"[OG Upload] Deleted old image: {filepath}")
        
        # Save to storage (works with local and S3)
        saved_path = default_storage.save(filepath, ContentFile(image_data))
        
        logger.info(f"[OG Upload] ✓ Saved OG image for cluster {cluster_id}: {saved_path}")
        
        return JsonResponse({
            'success': True,
            'cluster_id': cluster_id,
            'path': saved_path,
            'size_kb': round(image_size / 1024, 1)
        })
        
    except Exception as e:
        logger.error(f"[OG Upload] Error uploading OG image: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def cluster_evolution_json(request):
    """
    JSON endpoint for cluster evolution data (Sankey diagram).
    
    Query params:
        - runs: Number of recent runs to analyze (default: 5, max: 20)
    """
    from collections import defaultdict
    
    try:
        n_runs = int(request.GET.get('runs', 5))
        n_runs = min(max(n_runs, 2), 20)  # Between 2 and 20
        
        # Get recent completed runs
        runs = list(VoterClusterRun.objects.filter(
            status='completed'
        ).order_by('-created_at')[:n_runs])
        runs.reverse()  # Chronological order
        
        if len(runs) < 2:
            return JsonResponse({'error': 'Need at least 2 completed runs'}, status=404)
        
        # Build Sankey data
        nodes = []
        links = []
        node_idx = 0
        node_map = {}
        
        cluster_colors = [
            '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
            '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'
        ]
        
        # Build nodes
        for run in runs:
            clusters = run.clusters.filter(
                cluster_type='group'
            ).order_by('cluster_id')
            
            for cluster in clusters:
                node_key = f"{run.id}_{cluster.cluster_id}"
                node_map[node_key] = node_idx
                
                label = cluster.llm_name or f'Cluster {cluster.cluster_id}'
                nodes.append({
                    'label': f"{label} (n={cluster.size})",
                    'color': cluster_colors[cluster.cluster_id % len(cluster_colors)],
                })
                node_idx += 1
        
        # Build links between consecutive runs
        for i in range(len(runs) - 1):
            run1, run2 = runs[i], runs[i + 1]
            
            # Get memberships for both runs
            memberships1 = defaultdict(set)
            for m in run1.clusters.filter(
                cluster_type='group'
            ).prefetch_related('members'):
                for member in m.members.all():
                    voter_key = f'{member.voter_type}:{member.voter_id}'
                    memberships1[m.cluster_id].add(voter_key)
            
            memberships2 = defaultdict(set)
            for m in run2.clusters.filter(
                cluster_type='group'
            ).prefetch_related('members'):
                for member in m.members.all():
                    voter_key = f'{member.voter_type}:{member.voter_id}'
                    memberships2[m.cluster_id].add(voter_key)
            
            # Compute overlaps
            for c1_id, voters1 in memberships1.items():
                for c2_id, voters2 in memberships2.items():
                    overlap = len(voters1 & voters2)
                    if overlap >= 5:  # Filter noise
                        from_key = f"{run1.id}_{c1_id}"
                        to_key = f"{run2.id}_{c2_id}"
                        
                        # Determine relationship type
                        overlap_pct_from = overlap / len(voters1) * 100 if voters1 else 0
                        overlap_pct_to = overlap / len(voters2) * 100 if voters2 else 0
                        
                        if overlap_pct_from > 80 and overlap_pct_to > 80:
                            color = 'rgba(0, 200, 0, 0.4)'  # Continuation
                        elif overlap_pct_from > 30 and overlap_pct_to < 70:
                            color = 'rgba(255, 165, 0, 0.4)'  # Split
                        elif overlap_pct_from < 70 and overlap_pct_to > 30:
                            color = 'rgba(0, 100, 255, 0.4)'  # Merge
                        else:
                            color = 'rgba(100, 100, 100, 0.2)'  # Minor
                        
                        links.append({
                            'source': node_map[from_key],
                            'target': node_map[to_key],
                            'value': overlap,
                            'color': color,
                        })
        
        return JsonResponse({
            'data': [{
                'type': 'sankey',
                'node': {
                    'pad': 15,
                    'thickness': 20,
                    'line': {'color': 'black', 'width': 0.5},
                    'label': [n['label'] for n in nodes],
                    'color': [n['color'] for n in nodes],
                },
                'link': {
                    'source': [l['source'] for l in links],
                    'target': [l['target'] for l in links],
                    'value': [l['value'] for l in links],
                    'color': [l['color'] for l in links],
                }
            }],
            'layout': {
                'title': f'Evolución de Burbujas ({len(runs)} corridas)',
                'font': {'size': 12},
                'height': 600,
            },
            'runs': [
                {
                    'id': r.id,
                    'created_at': r.created_at.isoformat(),
                    'n_voters': r.n_voters,
                    'n_clusters': r.n_clusters,
                }
                for r in runs
            ]
        })
        
    except Exception as e:
        logger.error(f"Error generating cluster evolution data: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def cluster_og_image(request):
    """
    Serve Open Graph image for cluster sharing.
    
    ONLY serves user-uploaded images from real captures.
    No fallback, no generation - if there's no uploaded image, returns static logo.
    
    Query params:
        - cluster: Optional cluster ID
    """
    try:
        cluster_id_param = request.GET.get('cluster')
        
        # Log crawler info for debugging
        user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
        referer = request.META.get('HTTP_REFERER', 'No referer')
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', 'Unknown IP'))
        
        # Identify common crawlers
        crawler = 'Unknown'
        if 'whatsapp' in user_agent.lower():
            crawler = 'WhatsApp'
        elif 'facebookexternalhit' in user_agent.lower():
            crawler = 'Facebook'
        elif 'twitterbot' in user_agent.lower():
            crawler = 'Twitter'
        elif 'telegrambot' in user_agent.lower():
            crawler = 'Telegram'
        elif 'slackbot' in user_agent.lower():
            crawler = 'Slack'
        elif 'linkedinbot' in user_agent.lower():
            crawler = 'LinkedIn'
        
        logger.info(f"[OG Image] 🔍 Request from {crawler}")
        logger.info(f"[OG Image]    Cluster: {cluster_id_param}")
        logger.info(f"[OG Image]    IP: {ip}")
        logger.info(f"[OG Image]    Referer: {referer}")
        logger.info(f"[OG Image]    User-Agent: {user_agent[:100]}...")
        
        # Serve user-uploaded image if exists
        if cluster_id_param:
            filename = f'og-cluster-{cluster_id_param}.jpg'
            filepath = os.path.join('og-images', filename)
            logger.info(f"[OG Image]    Looking for: {filepath}")
            
            if default_storage.exists(filepath):
                try:
                    with default_storage.open(filepath, 'rb') as f:
                        image_data = f.read()
                        logger.info(f"[OG Image]    ✅ Serving user-captured image ({len(image_data)/1024:.1f} KB)")
                        return HttpResponse(image_data, content_type='image/jpeg')
                except Exception as e:
                    logger.error(f"[OG Image]    ❌ Error reading image: {e}")
        
        # No uploaded image - return static logo
        logger.info(f"[OG Image]    ℹ️  No uploaded image, redirecting to static logo")
        from django.templatetags.static import static
        from django.shortcuts import redirect
        
        # Redirect to static logo
        logo_url = static('core/logo.svg')
        return redirect(logo_url)
        
    except Exception as e:
        logger.error(f"[OG Image] Error: {e}", exc_info=True)
        from django.templatetags.static import static
        from django.shortcuts import redirect
        return redirect(static('core/logo.svg'))
