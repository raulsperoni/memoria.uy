"""
Bridge-builder identification and analysis.

Identifies voters who connect different opinion clusters, acting as bridges
between bubbles. These voters have voting patterns similar to multiple clusters.

Key insight: "Some people naturally connect different perspectives."
"""

import numpy as np
from collections import defaultdict
from sklearn.metrics.pairwise import euclidean_distances
import logging

logger = logging.getLogger(__name__)


def identify_bridge_builders(run, distance_threshold=0.5, min_connections=2):
    """
    Identify voters who act as bridges between clusters.
    
    A bridge-builder is someone whose projection is close to multiple cluster
    centroids, indicating they share voting patterns with different groups.
    
    Args:
        run: VoterClusterRun instance
        distance_threshold: max distance to centroid to be considered "close"
        min_connections: minimum number of clusters to connect
    
    Returns:
        list of dict: [
            {
                'voter_type': 'user'|'session',
                'voter_id': str,
                'assigned_cluster': int,
                'connected_clusters': [1, 3, 4],  # cluster IDs
                'distances': {1: 0.3, 3: 0.45, 4: 0.4},
                'bridge_strength': float (0-1),  # higher = stronger bridge
                'n_votes': int,
                'projection_x': float,
                'projection_y': float,
            }
        ]
    """
    clusters = run.clusters.filter(cluster_type='group').prefetch_related('members')
    projections = run.projections.all()
    
    if not clusters.exists() or not projections.exists():
        logger.warning(f"No data for bridge analysis in run {run.id}")
        return []
    
    # Build centroid positions
    cluster_centroids = {}
    for cluster in clusters:
        cluster_centroids[cluster.cluster_id] = np.array([
            cluster.centroid_x,
            cluster.centroid_y
        ])
    
    # Build voter assignment map
    voter_clusters = {}
    for cluster in clusters:
        for member in cluster.members.all():
            key = f"{member.voter_type}:{member.voter_id}"
            voter_clusters[key] = cluster.cluster_id
    
    # Analyze each voter
    bridges = []
    
    for proj in projections:
        voter_key = f"{proj.voter_type}:{proj.voter_id}"
        assigned_cluster = voter_clusters.get(voter_key)
        
        if assigned_cluster is None:
            continue
        
        voter_pos = np.array([proj.projection_x, proj.projection_y])
        
        # Calculate distance to all centroids
        distances = {}
        for cluster_id, centroid in cluster_centroids.items():
            dist = np.linalg.norm(voter_pos - centroid)
            distances[cluster_id] = float(dist)
        
        # Find clusters within threshold
        connected = [
            cid for cid, dist in distances.items()
            if dist <= distance_threshold
        ]
        
        # Must connect at least min_connections clusters
        if len(connected) < min_connections:
            continue
        
        # Calculate bridge strength
        # Stronger bridge = closer to multiple centroids
        # Normalize by average distance to connected centroids
        avg_distance = np.mean([distances[cid] for cid in connected])
        bridge_strength = 1.0 - (avg_distance / distance_threshold)
        bridge_strength = max(0.0, min(1.0, bridge_strength))
        
        bridges.append({
            'voter_type': proj.voter_type,
            'voter_id': proj.voter_id,
            'assigned_cluster': assigned_cluster,
            'connected_clusters': connected,
            'distances': distances,
            'bridge_strength': float(bridge_strength),
            'n_votes': proj.n_votes_cast,
            'projection_x': float(proj.projection_x),
            'projection_y': float(proj.projection_y),
        })
    
    # Sort by bridge strength (strongest first)
    bridges.sort(key=lambda x: x['bridge_strength'], reverse=True)
    
    logger.info(f"Identified {len(bridges)} bridge-builders in run {run.id}")
    
    return bridges


def calculate_bridge_strength(projection, centroid_a, centroid_b):
    """
    Calculate how well a voter bridges two specific clusters.
    
    Args:
        projection: (x, y) tuple
        centroid_a: (x, y) tuple
        centroid_b: (x, y) tuple
    
    Returns:
        float: bridge strength (0-1)
            1.0 = exactly between the two centroids
            0.0 = far from both
    """
    proj = np.array(projection)
    cent_a = np.array(centroid_a)
    cent_b = np.array(centroid_b)
    
    # Distance to each centroid
    dist_a = np.linalg.norm(proj - cent_a)
    dist_b = np.linalg.norm(proj - cent_b)
    
    # Distance between centroids
    centroid_distance = np.linalg.norm(cent_a - cent_b)
    
    if centroid_distance == 0:
        return 0.0
    
    # Ideal bridge position is midpoint
    midpoint = (cent_a + cent_b) / 2
    dist_to_midpoint = np.linalg.norm(proj - midpoint)
    
    # Normalize by centroid distance
    # Closer to midpoint = stronger bridge
    normalized_distance = dist_to_midpoint / (centroid_distance / 2)
    strength = max(0.0, 1.0 - normalized_distance)
    
    return float(strength)


def build_bridge_network_data(run, distance_threshold=0.5):
    """
    Build network graph data for visualization.
    
    Creates nodes (clusters + bridges) and edges (connections).
    
    Args:
        run: VoterClusterRun instance
        distance_threshold: threshold for bridge identification
    
    Returns:
        dict: {
            'nodes': [
                {
                    'id': 'cluster_1',
                    'type': 'cluster',
                    'label': 'Burbuja A',
                    'size': 100,
                    'x': 0.5,
                    'y': 0.3,
                },
                {
                    'id': 'voter_session:abc',
                    'type': 'bridge',
                    'strength': 0.8,
                    'n_votes': 45,
                    'x': 0.4,
                    'y': 0.35,
                },
            ],
            'edges': [
                {
                    'source': 'voter_session:abc',
                    'target': 'cluster_1',
                    'weight': 0.7,
                },
            ]
        }
    """
    clusters = run.clusters.filter(cluster_type='group')
    bridges = identify_bridge_builders(run, distance_threshold=distance_threshold)
    
    nodes = []
    edges = []
    
    # Add cluster nodes
    for cluster in clusters:
        nodes.append({
            'id': f'cluster_{cluster.cluster_id}',
            'type': 'cluster',
            'label': cluster.llm_name or f'Burbuja {cluster.cluster_id}',
            'description': cluster.llm_description or '',
            'size': cluster.size,
            'x': float(cluster.centroid_x),
            'y': float(cluster.centroid_y),
            'cluster_id': cluster.cluster_id,
        })
    
    # Add bridge nodes (limit to top bridges for visualization clarity)
    top_bridges = bridges[:50]  # Top 50 strongest bridges
    
    for bridge in top_bridges:
        voter_id = f"{bridge['voter_type']}:{bridge['voter_id']}"
        
        nodes.append({
            'id': f'voter_{voter_id}',
            'type': 'bridge',
            'strength': bridge['bridge_strength'],
            'n_votes': bridge['n_votes'],
            'x': bridge['projection_x'],
            'y': bridge['projection_y'],
            'assigned_cluster': bridge['assigned_cluster'],
            'connected_clusters': bridge['connected_clusters'],
        })
        
        # Add edges to connected clusters
        for cluster_id in bridge['connected_clusters']:
            distance = bridge['distances'][cluster_id]
            weight = 1.0 - (distance / distance_threshold)  # Closer = stronger edge
            
            edges.append({
                'source': f'voter_{voter_id}',
                'target': f'cluster_{cluster_id}',
                'weight': float(weight),
                'distance': float(distance),
            })
    
    return {
        'nodes': nodes,
        'edges': edges,
        'n_clusters': len(nodes) - len(top_bridges),
        'n_bridges': len(top_bridges),
    }


def analyze_bridge_activity(bridges):
    """
    Analyze voting activity patterns of bridge-builders.
    
    Args:
        bridges: list from identify_bridge_builders()
    
    Returns:
        dict: {
            'total_bridges': int,
            'avg_votes': float,
            'avg_connections': float,
            'strongest_bridge': dict,
            'most_active_bridge': dict,
        }
    """
    if not bridges:
        return {
            'total_bridges': 0,
            'avg_votes': 0.0,
            'avg_connections': 0.0,
            'strongest_bridge': None,
            'most_active_bridge': None,
        }
    
    total = len(bridges)
    avg_votes = np.mean([b['n_votes'] for b in bridges])
    avg_connections = np.mean([len(b['connected_clusters']) for b in bridges])
    
    strongest = max(bridges, key=lambda b: b['bridge_strength'])
    most_active = max(bridges, key=lambda b: b['n_votes'])
    
    return {
        'total_bridges': total,
        'avg_votes': float(avg_votes),
        'avg_connections': float(avg_connections),
        'strongest_bridge': strongest,
        'most_active_bridge': most_active,
    }


def get_bridge_vote_examples(run, bridge_voter_key, limit=10):
    """
    Get example votes from a bridge-builder to understand their pattern.
    
    Args:
        run: VoterClusterRun instance
        bridge_voter_key: "user:123" or "session:abc"
        limit: number of votes to return
    
    Returns:
        list of dict: vote examples with cluster opinions
    """
    from core.models import Voto, VoterClusterMembership
    
    voter_type, voter_id = bridge_voter_key.split(':', 1)
    
    # Get this voter's votes
    if voter_type == 'user':
        votes = Voto.objects.filter(usuario_id=voter_id)
    else:
        votes = Voto.objects.filter(session_key=voter_id)
    
    votes = votes.select_related('noticia').order_by('-fecha_voto')[:limit]
    
    # Get cluster opinions on same noticias
    clusters = run.clusters.filter(cluster_type='group')
    
    examples = []
    for vote in votes:
        # Get how each cluster voted on this noticia
        cluster_opinions = {}
        
        for cluster in clusters:
            pattern = cluster.voting_patterns.filter(noticia=vote.noticia).first()
            if pattern:
                cluster_opinions[cluster.cluster_id] = {
                    'majority': pattern.majority_opinion,
                    'consensus': pattern.consensus_score,
                }
        
        examples.append({
            'noticia': vote.noticia,
            'bridge_vote': vote.opinion,
            'cluster_opinions': cluster_opinions,
            'fecha': vote.fecha_voto,
        })
    
    return examples
