"""
Tests for consensus analysis module.
"""

import pytest
from django.contrib.auth import get_user_model
from core.models import Noticia, Voto, VoterClusterRun, VoterCluster, VoterClusterMembership, VoterProjection
from core.clustering.consensus import (
    calculate_cross_cluster_consensus,
    calculate_consensus_news,
    calculate_divisive_news,
    calculate_polarization_score,
)

User = get_user_model()


@pytest.mark.django_db
class TestConsensusCalculation:
    """Test consensus metric calculations."""
    
    def test_cross_cluster_consensus_basic(self, cluster_run_with_data):
        """Test basic cross-cluster consensus calculation."""
        run = cluster_run_with_data
        
        results = calculate_cross_cluster_consensus(run, min_votes_per_cluster=1)
        
        # Should return list of dicts
        assert isinstance(results, list)
        if results:
            assert 'consensus_score' in results[0]
            assert 'polarization_score' in results[0]
            assert 'noticia' in results[0]
            assert 0 <= results[0]['consensus_score'] <= 1
            assert 0 <= results[0]['polarization_score'] <= 1
    
    def test_consensus_news_filtering(self, cluster_run_with_data):
        """Test filtering for high consensus news."""
        run = cluster_run_with_data
        
        consensus_news = calculate_consensus_news(run, consensus_threshold=0.5, top_n=10)
        
        # All returned news should have consensus above threshold
        for item in consensus_news:
            assert item['consensus_score'] >= 0.5
        
        # Should be sorted by consensus (highest first)
        if len(consensus_news) > 1:
            assert consensus_news[0]['consensus_score'] >= consensus_news[-1]['consensus_score']
    
    def test_divisive_news_sorting(self, cluster_run_with_data):
        """Test divisive news sorting by polarization."""
        run = cluster_run_with_data
        
        divisive = calculate_divisive_news(run, top_n=10)
        
        # Should be sorted by polarization (highest first)
        if len(divisive) > 1:
            assert divisive[0]['polarization_score'] >= divisive[-1]['polarization_score']
    
    def test_polarization_score_structure(self, cluster_run_with_data):
        """Test polarization score returns correct structure."""
        run = cluster_run_with_data
        
        result = calculate_polarization_score(run)
        
        assert 'polarization_score' in result
        assert 'consensus_score' in result
        assert 'n_consensus_news' in result
        assert 'n_divisive_news' in result
        assert 'n_total_news' in result
        
        # Scores should be valid
        assert 0 <= result['polarization_score'] <= 1
        assert 0 <= result['consensus_score'] <= 1
        assert result['n_total_news'] >= 0
    
    def test_empty_run(self):
        """Test handling of run with no data."""
        run = VoterClusterRun.objects.create(
            status='completed',
            n_voters=0,
            n_noticias=0,
            n_clusters=0,
        )
        
        results = calculate_cross_cluster_consensus(run)
        assert results == []
        
        polarization = calculate_polarization_score(run)
        assert polarization['n_total_news'] == 0


@pytest.fixture
def cluster_run_with_data(db):
    """Create a clustering run with test data."""
    # Create users and news
    user1 = User.objects.create_user(username='user1', email='user1@test.com')
    user2 = User.objects.create_user(username='user2', email='user2@test.com')
    
    noticia1 = Noticia.objects.create(
        enlace='https://example.com/news1',
        meta_titulo='Test News 1',
    )
    noticia2 = Noticia.objects.create(
        enlace='https://example.com/news2',
        meta_titulo='Test News 2',
    )
    
    # Create votes
    Voto.objects.create(usuario=user1, noticia=noticia1, opinion='buena')
    Voto.objects.create(usuario=user2, noticia=noticia1, opinion='buena')
    Voto.objects.create(usuario=user1, noticia=noticia2, opinion='mala')
    Voto.objects.create(usuario=user2, noticia=noticia2, opinion='buena')
    
    # Create clustering run
    run = VoterClusterRun.objects.create(
        status='completed',
        n_voters=2,
        n_noticias=2,
        n_clusters=2,
    )
    
    # Create clusters
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
        centroid_x=1.0,
        centroid_y=1.0,
    )
    
    # Create memberships
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
    
    # Create projections
    VoterProjection.objects.create(
        run=run,
        voter_type='user',
        voter_id=str(user1.id),
        projection_x=0.0,
        projection_y=0.0,
        n_votes_cast=2,
    )
    VoterProjection.objects.create(
        run=run,
        voter_type='user',
        voter_id=str(user2.id),
        projection_x=1.0,
        projection_y=1.0,
        n_votes_cast=2,
    )
    
    return run
