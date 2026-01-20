"""
Tests for bridge-builder identification module.
"""

import pytest
import numpy as np
from django.contrib.auth import get_user_model
from core.models import VoterClusterRun, VoterCluster, VoterClusterMembership, VoterProjection
from core.clustering.bridges import (
    identify_bridge_builders,
    calculate_bridge_strength,
    build_bridge_network_data,
    analyze_bridge_activity,
)

User = get_user_model()


@pytest.mark.django_db
class TestBridgeIdentification:
    """Test bridge-builder identification."""
    
    def test_identify_bridges_basic(self, cluster_run_with_bridges):
        """Test basic bridge identification."""
        run = cluster_run_with_bridges
        
        bridges = identify_bridge_builders(run, distance_threshold=0.8, min_connections=2)
        
        # Should return list
        assert isinstance(bridges, list)
        
        # Check structure
        if bridges:
            bridge = bridges[0]
            assert 'voter_type' in bridge
            assert 'voter_id' in bridge
            assert 'connected_clusters' in bridge
            assert 'bridge_strength' in bridge
            assert 'n_votes' in bridge
            
            # Strength should be valid
            assert 0 <= bridge['bridge_strength'] <= 1
            
            # Should connect min_connections clusters
            assert len(bridge['connected_clusters']) >= 2
    
    def test_bridge_strength_calculation(self):
        """Test bridge strength calculation between two centroids."""
        # Bridge exactly at midpoint
        strength = calculate_bridge_strength(
            (0.5, 0.5),  # projection at midpoint
            (0.0, 0.0),  # centroid A
            (1.0, 1.0),  # centroid B
        )
        
        # Should have high strength (close to midpoint)
        assert strength > 0.8
        
        # Bridge far from both centroids
        strength_far = calculate_bridge_strength(
            (2.0, 2.0),  # far away
            (0.0, 0.0),
            (1.0, 1.0),
        )
        
        # Should have low strength
        assert strength_far < 0.5
    
    def test_bridge_network_data_structure(self, cluster_run_with_bridges):
        """Test network data structure for visualization."""
        run = cluster_run_with_bridges
        
        network = build_bridge_network_data(run, distance_threshold=0.8)
        
        assert 'nodes' in network
        assert 'edges' in network
        assert 'n_clusters' in network
        assert 'n_bridges' in network
        
        # Nodes should have cluster and bridge types
        node_types = {node['type'] for node in network['nodes']}
        if len(network['nodes']) > 0:
            assert 'cluster' in node_types or 'bridge' in node_types
        
        # Edges should connect bridges to clusters
        if network['edges']:
            edge = network['edges'][0]
            assert 'source' in edge
            assert 'target' in edge
            assert 'weight' in edge
            assert 0 <= edge['weight'] <= 1
    
    def test_bridge_activity_analysis(self, cluster_run_with_bridges):
        """Test bridge activity statistics."""
        run = cluster_run_with_bridges
        bridges = identify_bridge_builders(run, distance_threshold=0.8)
        
        stats = analyze_bridge_activity(bridges)
        
        assert 'total_bridges' in stats
        assert 'avg_votes' in stats
        assert 'avg_connections' in stats
        
        if bridges:
            assert stats['total_bridges'] == len(bridges)
            assert stats['avg_votes'] >= 0
            assert stats['avg_connections'] >= 2  # min_connections default
            assert 'strongest_bridge' in stats
            assert 'most_active_bridge' in stats
    
    def test_no_bridges_case(self, cluster_run_no_bridges):
        """Test handling when no bridges exist."""
        run = cluster_run_no_bridges
        
        bridges = identify_bridge_builders(run, distance_threshold=0.1)  # Very tight threshold
        
        assert bridges == []
        
        stats = analyze_bridge_activity(bridges)
        assert stats['total_bridges'] == 0


@pytest.fixture
def cluster_run_with_bridges(db):
    """Create a clustering run with bridge voters."""
    user1 = User.objects.create_user(username='user1')
    user2 = User.objects.create_user(username='user2')
    user3 = User.objects.create_user(username='user3')  # Bridge voter
    
    # Create run
    run = VoterClusterRun.objects.create(
        status='completed',
        n_voters=3,
        n_noticias=5,
        n_clusters=2,
    )
    
    # Create two clusters far apart
    cluster1 = VoterCluster.objects.create(
        run=run,
        cluster_type='group',
        cluster_id=1,
        size=1,
        centroid_x=0.0,
        centroid_y=0.0,
    )
    cluster2 = VoterCluster.objects.create(
        run=run,
        cluster_type='group',
        cluster_id=2,
        size=2,
        centroid_x=1.0,
        centroid_y=1.0,
    )
    
    # Create memberships
    VoterClusterMembership.objects.create(
        cluster=cluster1,
        voter_type='user',
        voter_id=str(user1.id),
        distance_to_centroid=0.1,
    )
    VoterClusterMembership.objects.create(
        cluster=cluster2,
        voter_type='user',
        voter_id=str(user2.id),
        distance_to_centroid=0.1,
    )
    VoterClusterMembership.objects.create(
        cluster=cluster2,
        voter_type='user',
        voter_id=str(user3.id),
        distance_to_centroid=0.5,
    )
    
    # Create projections - user3 is between clusters (bridge)
    VoterProjection.objects.create(
        run=run,
        voter_type='user',
        voter_id=str(user1.id),
        projection_x=0.0,
        projection_y=0.0,
        n_votes_cast=5,
    )
    VoterProjection.objects.create(
        run=run,
        voter_type='user',
        voter_id=str(user2.id),
        projection_x=1.0,
        projection_y=1.0,
        n_votes_cast=5,
    )
    VoterProjection.objects.create(
        run=run,
        voter_type='user',
        voter_id=str(user3.id),
        projection_x=0.5,  # Between clusters
        projection_y=0.5,
        n_votes_cast=10,  # More active
    )
    
    return run


@pytest.fixture
def cluster_run_no_bridges(db):
    """Create a clustering run with no bridges (tight clusters)."""
    user1 = User.objects.create_user(username='user1')
    user2 = User.objects.create_user(username='user2')
    
    run = VoterClusterRun.objects.create(
        status='completed',
        n_voters=2,
        n_noticias=5,
        n_clusters=2,
    )
    
    # Create two clusters very far apart
    cluster1 = VoterCluster.objects.create(
        run=run,
        cluster_type='group',
        cluster_id=1,
        size=1,
        centroid_x=0.0,
        centroid_y=0.0,
    )
    cluster2 = VoterCluster.objects.create(
        run=run,
        cluster_type='group',
        cluster_id=2,
        size=1,
        centroid_x=10.0,  # Very far
        centroid_y=10.0,
    )
    
    VoterClusterMembership.objects.create(
        cluster=cluster1,
        voter_type='user',
        voter_id=str(user1.id),
        distance_to_centroid=0.0,
    )
    VoterClusterMembership.objects.create(
        cluster=cluster2,
        voter_type='user',
        voter_id=str(user2.id),
        distance_to_centroid=0.0,
    )
    
    VoterProjection.objects.create(
        run=run,
        voter_type='user',
        voter_id=str(user1.id),
        projection_x=0.0,
        projection_y=0.0,
        n_votes_cast=5,
    )
    VoterProjection.objects.create(
        run=run,
        voter_type='user',
        voter_id=str(user2.id),
        projection_x=10.0,
        projection_y=10.0,
        n_votes_cast=5,
    )
    
    return run
