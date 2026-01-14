"""
Tests for voter clustering functionality.
"""

import pytest
import numpy as np
from scipy.sparse import lil_matrix
from django.contrib.auth.models import User
from core.models import Noticia, Voto, VoterClusterRun
from core.clustering import (
    build_vote_matrix,
    compute_sparsity_aware_pca,
    cluster_voters,
    group_clusters,
    compute_cluster_consensus,
    compute_voter_similarity,
)


@pytest.fixture
def sample_votes(db):
    """Create sample votes for testing."""
    # Create test users
    user1 = User.objects.create_user('user1', 'user1@test.com', 'pass')
    user2 = User.objects.create_user('user2', 'user2@test.com', 'pass')

    # Create test noticias
    noticia1 = Noticia.objects.create(
        enlace='http://test1.com',
        meta_titulo='Test Article 1'
    )
    noticia2 = Noticia.objects.create(
        enlace='http://test2.com',
        meta_titulo='Test Article 2'
    )
    noticia3 = Noticia.objects.create(
        enlace='http://test3.com',
        meta_titulo='Test Article 3'
    )

    # Create votes
    # User1: buena, buena, mala
    Voto.objects.create(usuario=user1, noticia=noticia1, opinion='buena')
    Voto.objects.create(usuario=user1, noticia=noticia2, opinion='buena')
    Voto.objects.create(usuario=user1, noticia=noticia3, opinion='mala')

    # User2: buena, mala, mala
    Voto.objects.create(usuario=user2, noticia=noticia1, opinion='buena')
    Voto.objects.create(usuario=user2, noticia=noticia2, opinion='mala')
    Voto.objects.create(usuario=user2, noticia=noticia3, opinion='mala')

    # Session votes
    Voto.objects.create(
        session_key='session1',
        noticia=noticia1,
        opinion='neutral'
    )
    Voto.objects.create(
        session_key='session1',
        noticia=noticia2,
        opinion='neutral'
    )
    Voto.objects.create(
        session_key='session1',
        noticia=noticia3,
        opinion='neutral'
    )

    return {
        'users': [user1, user2],
        'noticias': [noticia1, noticia2, noticia3]
    }


def test_build_vote_matrix(sample_votes):
    """Test vote matrix construction."""
    vote_matrix, voter_ids, noticia_ids = build_vote_matrix(
        time_window_days=30,
        min_votes_per_voter=3
    )

    # Should have 3 voters (2 users + 1 session) and 3 noticias
    assert vote_matrix.shape[0] == 3  # 3 voters
    assert vote_matrix.shape[1] == 3  # 3 noticias
    assert len(voter_ids) == 3
    assert len(noticia_ids) == 3

    # Check vote encoding (buena=1, neutral=0, mala=-1)
    # User1's votes should be [1, 1, -1]
    # User2's votes should be [1, -1, -1]
    # Session1's votes should be [0, 0, 0]
    # Note: neutral (0) votes are sparse, so nnz will be 6 not 9
    assert vote_matrix.nnz == 6  # Non-zero votes only


def test_compute_sparsity_aware_pca():
    """Test PCA with sparse matrix."""
    # Create small test matrix
    n_voters = 10
    n_noticias = 5
    vote_matrix = lil_matrix((n_voters, n_noticias), dtype=np.float32)

    # Fill with random votes
    np.random.seed(42)
    for i in range(n_voters):
        for j in range(n_noticias):
            if np.random.rand() > 0.3:  # 70% density
                vote_matrix[i, j] = np.random.choice([-1, 0, 1])

    pca_result = compute_sparsity_aware_pca(vote_matrix, n_components=2)

    # Check output shapes
    assert pca_result['voter_projections'].shape == (n_voters, 2)
    assert pca_result['noticia_projections'].shape == (n_noticias, 2)
    assert len(pca_result['variance_explained']) == 2
    assert len(pca_result['voter_vote_counts']) == n_voters
    assert len(pca_result['noticia_vote_counts']) == n_noticias
    assert all(pca_result['voter_vote_counts'] > 0)


def test_cluster_voters():
    """Test k-means clustering."""
    # Create simple 2D projections
    np.random.seed(42)
    projections = np.random.randn(20, 2)
    voter_weights = np.ones(20)

    labels, centroids, inertia = cluster_voters(
        projections,
        voter_weights,
        k=3
    )

    # Check outputs
    assert len(labels) == 20
    assert centroids.shape == (3, 2)
    assert inertia > 0
    assert len(np.unique(labels)) <= 3


def test_group_clusters():
    """Test hierarchical group clustering."""
    np.random.seed(42)

    # Create base labels (simulate base clustering)
    base_labels = np.random.randint(0, 10, size=50)

    # Create projections
    projections = np.random.randn(50, 2)

    group_labels, best_k, silhouette_scores = group_clusters(
        base_labels,
        projections,
        k_range=(2, 4)
    )

    # Check outputs
    assert len(group_labels) == 50
    assert 2 <= best_k <= 4
    assert len(silhouette_scores) > 0


def test_compute_cluster_consensus():
    """Test consensus score calculation."""
    # High consensus case
    cluster_votes = {
        1: {'buena': 9, 'mala': 1, 'neutral': 0},
        2: {'buena': 8, 'mala': 2, 'neutral': 0},
    }
    consensus = compute_cluster_consensus(cluster_votes)
    # Consensus = avg((9/10), (8/10)) = 0.85
    assert 0.8 <= consensus <= 0.9  # Should be high

    # Low consensus case
    cluster_votes = {
        1: {'buena': 3, 'mala': 4, 'neutral': 3},
        2: {'buena': 4, 'mala': 3, 'neutral': 3},
    }
    consensus = compute_cluster_consensus(cluster_votes)
    # Consensus = avg((4/10), (4/10)) = 0.4
    assert 0.3 <= consensus <= 0.5  # Should be low


def test_compute_voter_similarity():
    """Test voter similarity calculation."""
    # Identical votes
    voter_a = {1: 'buena', 2: 'buena', 3: 'mala'}
    voter_b = {1: 'buena', 2: 'buena', 3: 'mala'}
    similarity = compute_voter_similarity(voter_a, voter_b)
    assert similarity == 1.0

    # Complete disagreement
    voter_a = {1: 'buena', 2: 'buena', 3: 'buena'}
    voter_b = {1: 'mala', 2: 'mala', 3: 'mala'}
    similarity = compute_voter_similarity(voter_a, voter_b)
    assert similarity == 0.0

    # Partial agreement
    voter_a = {1: 'buena', 2: 'buena', 3: 'mala'}
    voter_b = {1: 'buena', 2: 'mala', 3: 'mala'}
    similarity = compute_voter_similarity(voter_a, voter_b)
    assert similarity == 2/3  # 2 out of 3 agree

    # No overlap
    voter_a = {1: 'buena', 2: 'buena'}
    voter_b = {3: 'mala', 4: 'mala'}
    similarity = compute_voter_similarity(voter_a, voter_b)
    assert similarity is None


def test_voter_cluster_run_creation(db):
    """Test VoterClusterRun model."""
    run = VoterClusterRun.objects.create(
        status='pending',
        parameters={'time_window_days': 30}
    )

    assert run.id is not None
    assert run.status == 'pending'
    assert run.n_voters == 0
    assert run.n_clusters == 0


@pytest.mark.django_db
def test_build_vote_matrix_empty_database():
    """Test vote matrix with no votes."""
    vote_matrix, voter_ids, noticia_ids = build_vote_matrix(
        time_window_days=30,
        min_votes_per_voter=3
    )

    # Should return empty matrix
    assert vote_matrix.shape == (0, 0)
    assert len(voter_ids) == 0
    assert len(noticia_ids) == 0


@pytest.mark.django_db
def test_similar_profiles_cluster_together():
    """
    Voters with nearly identical vote patterns should land in the same cluster.
    Create two mirrored groups of voters and verify k-means separates them.
    """
    # Four noticias with clear opposing opinions
    noticias = [
        Noticia.objects.create(enlace=f"http://test{i}.com", meta_titulo=f"Test {i}")
        for i in range(4)
    ]

    pattern_a = ["buena", "buena", "mala", "mala"]
    pattern_b = ["mala", "mala", "buena", "buena"]

    def create_user_with_votes(username, pattern):
        user = User.objects.create_user(username, f"{username}@test.com", "pass")
        for noticia, opinion in zip(noticias, pattern):
            Voto.objects.create(usuario=user, noticia=noticia, opinion=opinion)
        return user

    group_a = [create_user_with_votes(f"group_a_{i}", pattern_a) for i in range(3)]
    group_b = [create_user_with_votes(f"group_b_{i}", pattern_b) for i in range(3)]

    vote_matrix, voter_ids, _ = build_vote_matrix(
        time_window_days=365,
        min_votes_per_voter=4,
    )

    # 6 voters × 4 noticias, all voters qualify
    assert vote_matrix.shape == (6, 4)
    assert len(voter_ids) == 6

    pca_result = compute_sparsity_aware_pca(vote_matrix)
    projections = pca_result['voter_projections']
    vote_counts = pca_result['voter_vote_counts']
    labels, _, _ = cluster_voters(projections, vote_counts, k=2)

    # Map user IDs to matrix row indices
    user_index = {
        voter_id[1]: idx for idx, voter_id in enumerate(voter_ids) if voter_id[0] == "user"
    }

    label_a = labels[user_index[str(group_a[0].id)]]
    label_b = labels[user_index[str(group_b[0].id)]]

    # All A users share label_a, all B users share label_b, and they differ
    assert label_a != label_b
    for user in group_a:
        assert labels[user_index[str(user.id)]] == label_a
    for user in group_b:
        assert labels[user_index[str(user.id)]] == label_b
