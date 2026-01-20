"""
Cross-cluster consensus analysis.

Identifies news articles that generate agreement or division across bubbles.
Key insight: "We agree more than we think."

References:
- Polis consensus/divisive statements methodology
- See SCIENTIFIC.md for clustering foundations
"""

import numpy as np
from collections import defaultdict, Counter
from django.db.models import Count, Q, Prefetch
import logging

logger = logging.getLogger(__name__)


def calculate_cross_cluster_consensus(run, min_votes_per_cluster=3):
    """
    Calculate consensus score for each noticia across all clusters.
    
    High consensus = most clusters vote similarly.
    Low consensus (divisive) = clusters disagree.
    
    Args:
        run: VoterClusterRun instance
        min_votes_per_cluster: minimum votes per cluster to consider noticia
    
    Returns:
        list of dict: [
            {
                'noticia': Noticia instance,
                'noticia_id': int,
                'consensus_score': float (0-1),
                'polarization_score': float (0-1),
                'cluster_votes': {
                    cluster_id: {
                        'buena': 0.7,  # proportion
                        'mala': 0.2,
                        'neutral': 0.1,
                        'total_votes': 20
                    }
                },
                'majority_opinion': 'buena'|'mala'|'neutral',
                'agreement_rate': float (0-1),  # % of clusters agreeing with majority
            }
        ]
    """
    from core.models import Noticia, Voto
    
    clusters = run.clusters.filter(cluster_type='group').prefetch_related('members')
    
    if not clusters.exists():
        logger.warning(f"No group clusters found for run {run.id}")
        return []
    
    # Build map of voter_id -> cluster_id
    voter_to_cluster = {}
    for cluster in clusters:
        for member in cluster.members.all():
            key = f"{member.voter_type}:{member.voter_id}"
            voter_to_cluster[key] = cluster.cluster_id
    
    # Get all votes for voters in this clustering
    all_votes = Voto.objects.select_related('noticia').all()
    
    # Aggregate votes by noticia and cluster
    noticia_cluster_votes = defaultdict(lambda: defaultdict(lambda: {'buena': 0, 'mala': 0, 'neutral': 0}))
    
    for vote in all_votes:
        # Identify voter
        if vote.usuario_id:
            voter_key = f"user:{vote.usuario_id}"
        elif vote.session_key:
            voter_key = f"session:{vote.session_key}"
        else:
            continue
        
        cluster_id = voter_to_cluster.get(voter_key)
        if cluster_id is None:
            continue
        
        noticia_cluster_votes[vote.noticia_id][cluster_id][vote.opinion] += 1
    
    # Calculate consensus metrics for each noticia
    results = []
    
    for noticia_id, cluster_data in noticia_cluster_votes.items():
        # Filter: need minimum votes per cluster
        valid_clusters = {
            cid: votes for cid, votes in cluster_data.items()
            if sum(votes.values()) >= min_votes_per_cluster
        }
        
        if len(valid_clusters) < 2:  # Need at least 2 clusters for consensus
            continue
        
        # Calculate proportions for each cluster
        cluster_votes = {}
        cluster_majorities = []
        
        for cluster_id, votes in valid_clusters.items():
            total = sum(votes.values())
            proportions = {
                'buena': votes['buena'] / total,
                'mala': votes['mala'] / total,
                'neutral': votes['neutral'] / total,
                'total_votes': total
            }
            cluster_votes[cluster_id] = proportions
            
            # Majority opinion for this cluster
            majority = max(proportions.items(), key=lambda x: x[0] != 'total_votes' and x[1])
            cluster_majorities.append(majority[0])
        
        # Overall majority across all clusters
        majority_counter = Counter(cluster_majorities)
        overall_majority = majority_counter.most_common(1)[0][0]
        agreement_rate = majority_counter[overall_majority] / len(cluster_majorities)
        
        # Consensus score: how much do clusters agree?
        # High = most clusters have same majority opinion
        consensus_score = agreement_rate
        
        # Polarization score: variance in opinions across clusters
        # Extract buena proportions for variance calculation
        buena_proportions = [cv['buena'] for cv in cluster_votes.values()]
        polarization_score = float(np.var(buena_proportions))
        
        try:
            noticia = Noticia.objects.get(id=noticia_id)
        except Noticia.DoesNotExist:
            continue
        
        results.append({
            'noticia': noticia,
            'noticia_id': noticia_id,
            'consensus_score': consensus_score,
            'polarization_score': polarization_score,
            'cluster_votes': cluster_votes,
            'majority_opinion': overall_majority,
            'agreement_rate': agreement_rate,
            'n_clusters_voted': len(valid_clusters),
        })
    
    # Sort by consensus score (highest first)
    results.sort(key=lambda x: x['consensus_score'], reverse=True)
    
    return results


def calculate_divisive_news(run, min_votes_per_cluster=3, top_n=20):
    """
    Identify the most divisive news articles.
    
    Divisive = high polarization, clusters disagree strongly.
    
    Args:
        run: VoterClusterRun instance
        min_votes_per_cluster: minimum votes to consider
        top_n: return top N most divisive
    
    Returns:
        list of dict: same structure as calculate_cross_cluster_consensus
    """
    all_results = calculate_cross_cluster_consensus(run, min_votes_per_cluster)
    
    # Sort by polarization (highest first)
    divisive = sorted(all_results, key=lambda x: x['polarization_score'], reverse=True)
    
    return divisive[:top_n]


def calculate_consensus_news(run, min_votes_per_cluster=3, consensus_threshold=0.7, top_n=20):
    """
    Identify news with highest cross-cluster consensus.
    
    Args:
        run: VoterClusterRun instance
        min_votes_per_cluster: minimum votes to consider
        consensus_threshold: minimum agreement rate
        top_n: return top N
    
    Returns:
        list of dict: news with high consensus
    """
    all_results = calculate_cross_cluster_consensus(run, min_votes_per_cluster)
    
    # Filter by consensus threshold
    consensus_news = [r for r in all_results if r['consensus_score'] >= consensus_threshold]
    
    # Already sorted by consensus_score
    return consensus_news[:top_n]


def calculate_polarization_score(run):
    """
    Calculate overall polarization score for a clustering run.
    
    Returns:
        dict: {
            'polarization_score': float (0-1),
            'consensus_score': float (0-1),
            'n_consensus_news': int,
            'n_divisive_news': int,
            'n_total_news': int,
        }
    """
    all_results = calculate_cross_cluster_consensus(run, min_votes_per_cluster=3)
    
    if not all_results:
        return {
            'polarization_score': 0.0,
            'consensus_score': 0.0,
            'n_consensus_news': 0,
            'n_divisive_news': 0,
            'n_total_news': 0,
        }
    
    # Average polarization
    avg_polarization = np.mean([r['polarization_score'] for r in all_results])
    avg_consensus = np.mean([r['consensus_score'] for r in all_results])
    
    # Count consensus vs divisive
    n_consensus = len([r for r in all_results if r['consensus_score'] >= 0.7])
    n_divisive = len([r for r in all_results if r['polarization_score'] >= 0.15])
    
    return {
        'polarization_score': float(avg_polarization),
        'consensus_score': float(avg_consensus),
        'n_consensus_news': n_consensus,
        'n_divisive_news': n_divisive,
        'n_total_news': len(all_results),
    }


def get_consensus_by_entity_type(run):
    """
    Analyze consensus patterns by entity type (personas, organizaciones, lugares).
    
    Returns:
        dict: {
            'personas': {'consensus': 0.8, 'polarization': 0.1},
            'organizaciones': {'consensus': 0.6, 'polarization': 0.2},
            'lugares': {'consensus': 0.7, 'polarization': 0.15},
        }
    """
    from core.models import NoticiaEntidad
    
    consensus_results = calculate_cross_cluster_consensus(run, min_votes_per_cluster=3)
    
    # Map noticia_id -> metrics
    noticia_metrics = {
        r['noticia_id']: {
            'consensus': r['consensus_score'],
            'polarization': r['polarization_score']
        }
        for r in consensus_results
    }
    
    # Group by entity type
    entity_types = ['persona', 'organizacion', 'lugar']
    results = {}
    
    for entity_type in entity_types:
        # Get noticias with this entity type
        noticias_with_type = NoticiaEntidad.objects.filter(
            entidad__tipo=entity_type,
            noticia_id__in=noticia_metrics.keys()
        ).values_list('noticia_id', flat=True).distinct()
        
        if noticias_with_type:
            metrics = [noticia_metrics[nid] for nid in noticias_with_type]
            results[entity_type] = {
                'consensus': float(np.mean([m['consensus'] for m in metrics])),
                'polarization': float(np.mean([m['polarization'] for m in metrics])),
                'n_news': len(metrics),
            }
        else:
            results[entity_type] = {
                'consensus': 0.0,
                'polarization': 0.0,
                'n_news': 0,
            }
    
    return results
