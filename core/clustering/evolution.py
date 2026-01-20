"""
Temporal evolution and stability analysis of clusters.

Tracks how clusters change over time: splits, merges, stability, opinion drift.

Key insight: "Understanding how opinion clusters evolve reveals societal shifts."
"""

import numpy as np
from collections import defaultdict
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


def calculate_stability_index(run1, run2):
    """
    Compare two consecutive clustering runs to measure stability.
    
    High stability = voters stay in same clusters
    Low stability = major reshuffling
    
    Args:
        run1: Earlier VoterClusterRun
        run2: Later VoterClusterRun
    
    Returns:
        dict: {
            'voter_retention': float (0-1),  # % voters in same relative cluster
            'cluster_persistence': [
                {
                    'run1_cluster_id': 1,
                    'run2_cluster_id': 2,
                    'retention': 0.88,
                    'overlap_count': 45,
                    'relationship': 'continuation'|'split'|'merge'|'new'
                },
            ],
            'stability_score': float (0-1),  # overall stability
        }
    """
    # Get memberships for both runs
    clusters1 = run1.clusters.filter(cluster_type='group').prefetch_related('members')
    clusters2 = run2.clusters.filter(cluster_type='group').prefetch_related('members')
    
    # Build voter -> cluster maps
    memberships1 = defaultdict(set)  # cluster_id -> set of voter keys
    memberships2 = defaultdict(set)
    
    for cluster in clusters1:
        for member in cluster.members.all():
            voter_key = f'{member.voter_type}:{member.voter_id}'
            memberships1[cluster.cluster_id].add(voter_key)
    
    for cluster in clusters2:
        for member in cluster.members.all():
            voter_key = f'{member.voter_type}:{member.voter_id}'
            memberships2[cluster.cluster_id].add(voter_key)
    
    # Find common voters
    voters1 = set().union(*memberships1.values())
    voters2 = set().union(*memberships2.values())
    common_voters = voters1 & voters2
    
    if not common_voters:
        return {
            'voter_retention': 0.0,
            'cluster_persistence': [],
            'stability_score': 0.0,
        }
    
    # Build inverse maps (voter -> cluster_id)
    voter_to_cluster1 = {}
    voter_to_cluster2 = {}
    
    for cid, voters in memberships1.items():
        for voter in voters:
            voter_to_cluster1[voter] = cid
    
    for cid, voters in memberships2.items():
        for voter in voters:
            voter_to_cluster2[voter] = cid
    
    # Calculate overlap matrix
    overlap_matrix = defaultdict(lambda: defaultdict(int))
    
    for voter in common_voters:
        c1 = voter_to_cluster1.get(voter)
        c2 = voter_to_cluster2.get(voter)
        if c1 is not None and c2 is not None:
            overlap_matrix[c1][c2] += 1
    
    # Analyze each cluster pair
    cluster_persistence = []
    
    for c1_id in memberships1.keys():
        c1_voters = memberships1[c1_id]
        c1_common = c1_voters & common_voters
        
        if not c1_common:
            continue
        
        # Find best matching cluster in run2
        best_overlap = 0
        best_c2 = None
        
        for c2_id in memberships2.keys():
            overlap = overlap_matrix[c1_id][c2_id]
            if overlap > best_overlap:
                best_overlap = overlap
                best_c2 = c2_id
        
        if best_c2 is None:
            continue
        
        c2_voters = memberships2[best_c2]
        c2_common = c2_voters & common_voters
        
        # Calculate retention rate
        retention_from_c1 = best_overlap / len(c1_common) if c1_common else 0
        retention_from_c2 = best_overlap / len(c2_common) if c2_common else 0
        
        # Determine relationship type
        if retention_from_c1 > 0.8 and retention_from_c2 > 0.8:
            relationship = 'continuation'
        elif retention_from_c1 > 0.5 and retention_from_c2 < 0.7:
            relationship = 'split'
        elif retention_from_c1 < 0.7 and retention_from_c2 > 0.5:
            relationship = 'merge'
        else:
            relationship = 'shuffle'
        
        cluster_persistence.append({
            'run1_cluster_id': c1_id,
            'run2_cluster_id': best_c2,
            'retention_from_run1': float(retention_from_c1),
            'retention_from_run2': float(retention_from_c2),
            'overlap_count': best_overlap,
            'relationship': relationship,
        })
    
    # Overall stability: weighted average of retention rates
    if cluster_persistence:
        total_voters = sum(cp['overlap_count'] for cp in cluster_persistence)
        weighted_retention = sum(
            cp['overlap_count'] * cp['retention_from_run1']
            for cp in cluster_persistence
        ) / total_voters if total_voters > 0 else 0
    else:
        weighted_retention = 0
    
    return {
        'voter_retention': float(weighted_retention),
        'cluster_persistence': cluster_persistence,
        'stability_score': float(weighted_retention),
        'n_common_voters': len(common_voters),
        'n_voters_run1': len(voters1),
        'n_voters_run2': len(voters2),
    }


def track_cluster_lineage(runs, min_overlap=5):
    """
    Track cluster lineage across multiple runs.
    
    Builds a graph showing how clusters split, merge, and evolve.
    
    Args:
        runs: list of VoterClusterRun instances (ordered by time)
        min_overlap: minimum voter overlap to consider relationship
    
    Returns:
        list of dict: [
            {
                'run_id': int,
                'cluster_id': int,
                'predecessors': [{'run_id': int, 'cluster_id': int, 'overlap': int}],
                'successors': [{'run_id': int, 'cluster_id': int, 'overlap': int}],
                'stability': float,
            }
        ]
    """
    lineage = []
    
    for i, run in enumerate(runs):
        clusters = run.clusters.filter(cluster_type='group').prefetch_related('members')
        
        # Build membership for this run
        memberships = defaultdict(set)
        for cluster in clusters:
            for member in cluster.members.all():
                voter_key = f'{member.voter_type}:{member.voter_id}'
                memberships[cluster.cluster_id].add(voter_key)
        
        # Compare with previous run
        predecessors_map = defaultdict(list)
        if i > 0:
            prev_run = runs[i - 1]
            prev_clusters = prev_run.clusters.filter(cluster_type='group').prefetch_related('members')
            prev_memberships = defaultdict(set)
            
            for cluster in prev_clusters:
                for member in cluster.members.all():
                    voter_key = f'{member.voter_type}:{member.voter_id}'
                    prev_memberships[cluster.cluster_id].add(voter_key)
            
            # Calculate overlaps
            for curr_cid, curr_voters in memberships.items():
                for prev_cid, prev_voters in prev_memberships.items():
                    overlap = len(curr_voters & prev_voters)
                    if overlap >= min_overlap:
                        predecessors_map[curr_cid].append({
                            'run_id': prev_run.id,
                            'cluster_id': prev_cid,
                            'overlap': overlap,
                        })
        
        # Compare with next run
        successors_map = defaultdict(list)
        if i < len(runs) - 1:
            next_run = runs[i + 1]
            next_clusters = next_run.clusters.filter(cluster_type='group').prefetch_related('members')
            next_memberships = defaultdict(set)
            
            for cluster in next_clusters:
                for member in cluster.members.all():
                    voter_key = f'{member.voter_type}:{member.voter_id}'
                    next_memberships[cluster.cluster_id].add(voter_key)
            
            # Calculate overlaps
            for curr_cid, curr_voters in memberships.items():
                for next_cid, next_voters in next_memberships.items():
                    overlap = len(curr_voters & next_voters)
                    if overlap >= min_overlap:
                        successors_map[curr_cid].append({
                            'run_id': next_run.id,
                            'cluster_id': next_cid,
                            'overlap': overlap,
                        })
        
        # Build lineage entries
        for cluster_id, voters in memberships.items():
            predecessors = predecessors_map.get(cluster_id, [])
            successors = successors_map.get(cluster_id, [])
            
            # Stability: ratio of largest successor overlap to cluster size
            if successors:
                max_successor_overlap = max(s['overlap'] for s in successors)
                stability = max_successor_overlap / len(voters) if voters else 0
            else:
                stability = 0
            
            lineage.append({
                'run_id': run.id,
                'cluster_id': cluster_id,
                'size': len(voters),
                'predecessors': predecessors,
                'successors': successors,
                'stability': float(stability),
            })
    
    return lineage


def analyze_temporal_drift(run_current, run_past, noticia_ids=None):
    """
    Analyze if clusters changed their opinions on specific topics.
    
    Compares voting patterns between two runs to detect opinion drift.
    
    Args:
        run_current: Recent VoterClusterRun
        run_past: Earlier VoterClusterRun
        noticia_ids: Optional list of noticia IDs to analyze (default: all common)
    
    Returns:
        list of dict: [
            {
                'cluster_id': int,
                'noticia_id': int,
                'noticia': Noticia,
                'opinion_past': 'buena'|'mala'|'neutral',
                'opinion_current': 'buena'|'mala'|'neutral',
                'changed': bool,
                'drift_score': float,  # magnitude of change
            }
        ]
    """
    from core.models import Noticia
    
    # Get voting patterns for both runs
    clusters_past = run_past.clusters.filter(cluster_type='group')
    clusters_current = run_current.clusters.filter(cluster_type='group')
    
    # Match clusters between runs (by overlap)
    stability = calculate_stability_index(run_past, run_current)
    cluster_matches = {}  # past_id -> current_id
    
    for persistence in stability['cluster_persistence']:
        if persistence['relationship'] in ['continuation', 'shuffle']:
            cluster_matches[persistence['run1_cluster_id']] = persistence['run2_cluster_id']
    
    drift_results = []
    
    for past_id, current_id in cluster_matches.items():
        cluster_past = clusters_past.filter(cluster_id=past_id).first()
        cluster_current = clusters_current.filter(cluster_id=current_id).first()
        
        if not cluster_past or not cluster_current:
            continue
        
        # Get voting patterns
        patterns_past = {
            p.noticia_id: p
            for p in cluster_past.voting_patterns.all()
        }
        patterns_current = {
            p.noticia_id: p
            for p in cluster_current.voting_patterns.all()
        }
        
        # Find common noticias
        common_noticias = set(patterns_past.keys()) & set(patterns_current.keys())
        
        if noticia_ids:
            common_noticias &= set(noticia_ids)
        
        for noticia_id in common_noticias:
            past_pattern = patterns_past[noticia_id]
            current_pattern = patterns_current[noticia_id]
            
            opinion_changed = past_pattern.majority_opinion != current_pattern.majority_opinion
            
            # Calculate drift magnitude (change in vote distribution)
            # For simplicity, use difference in consensus scores
            drift_score = abs(
                current_pattern.consensus_score - past_pattern.consensus_score
            )
            
            try:
                noticia = Noticia.objects.get(id=noticia_id)
            except Noticia.DoesNotExist:
                continue
            
            if opinion_changed or drift_score > 0.2:  # Significant drift
                drift_results.append({
                    'cluster_id': current_id,
                    'noticia_id': noticia_id,
                    'noticia': noticia,
                    'opinion_past': past_pattern.majority_opinion,
                    'opinion_current': current_pattern.majority_opinion,
                    'changed': opinion_changed,
                    'drift_score': float(drift_score),
                })
    
    # Sort by drift magnitude
    drift_results.sort(key=lambda x: x['drift_score'], reverse=True)
    
    return drift_results


def calculate_polarization_timeline(runs):
    """
    Calculate polarization metrics over time.
    
    Args:
        runs: list of VoterClusterRun instances (ordered by time)
    
    Returns:
        list of dict: [
            {
                'run_id': int,
                'date': datetime,
                'polarization_score': float,
                'consensus_score': float,
                'n_clusters': int,
                'avg_cluster_size': float,
                'silhouette_score': float,
            }
        ]
    """
    from core.clustering.consensus import calculate_polarization_score
    
    timeline = []
    
    for run in runs:
        try:
            polarization_data = calculate_polarization_score(run)
            
            clusters = run.clusters.filter(cluster_type='group')
            avg_size = np.mean([c.size for c in clusters]) if clusters.exists() else 0
            
            timeline.append({
                'run_id': run.id,
                'date': run.created_at,
                'polarization_score': polarization_data['polarization_score'],
                'consensus_score': polarization_data['consensus_score'],
                'n_clusters': run.n_clusters,
                'avg_cluster_size': float(avg_size),
                'silhouette_score': run.parameters.get('silhouette_score', 0),
                'n_voters': run.n_voters,
            })
        except Exception as e:
            logger.error(f"Error calculating metrics for run {run.id}: {e}")
            continue
    
    return timeline


def get_metrics_over_time(runs, metric='polarization'):
    """
    Extract a specific metric over time for plotting.
    
    Args:
        runs: list of VoterClusterRun instances
        metric: 'polarization'|'consensus'|'n_clusters'|'silhouette'
    
    Returns:
        dict: {
            'dates': [datetime, ...],
            'values': [float, ...],
        }
    """
    timeline = calculate_polarization_timeline(runs)
    
    metric_map = {
        'polarization': 'polarization_score',
        'consensus': 'consensus_score',
        'n_clusters': 'n_clusters',
        'silhouette': 'silhouette_score',
        'avg_size': 'avg_cluster_size',
    }
    
    metric_key = metric_map.get(metric, 'polarization_score')
    
    return {
        'dates': [t['date'].isoformat() for t in timeline],
        'values': [t[metric_key] for t in timeline],
    }
