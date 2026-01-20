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
    compute_cluster_entities,
    compute_cluster_voting_aggregation,
)


@pytest.fixture
def sample_votes(db):
    """Create sample votes for testing."""
    # Create test users
    user1 = User.objects.create_user("user1", "user1@test.com", "pass")
    user2 = User.objects.create_user("user2", "user2@test.com", "pass")

    # Create test noticias
    noticia1 = Noticia.objects.create(
        enlace="http://test1.com", meta_titulo="Test Article 1"
    )
    noticia2 = Noticia.objects.create(
        enlace="http://test2.com", meta_titulo="Test Article 2"
    )
    noticia3 = Noticia.objects.create(
        enlace="http://test3.com", meta_titulo="Test Article 3"
    )

    # Create votes
    # User1: buena, buena, mala
    Voto.objects.create(usuario=user1, noticia=noticia1, opinion="buena")
    Voto.objects.create(usuario=user1, noticia=noticia2, opinion="buena")
    Voto.objects.create(usuario=user1, noticia=noticia3, opinion="mala")

    # User2: buena, mala, mala
    Voto.objects.create(usuario=user2, noticia=noticia1, opinion="buena")
    Voto.objects.create(usuario=user2, noticia=noticia2, opinion="mala")
    Voto.objects.create(usuario=user2, noticia=noticia3, opinion="mala")

    # Session votes
    Voto.objects.create(session_key="session1", noticia=noticia1, opinion="neutral")
    Voto.objects.create(session_key="session1", noticia=noticia2, opinion="neutral")
    Voto.objects.create(session_key="session1", noticia=noticia3, opinion="neutral")

    return {"users": [user1, user2], "noticias": [noticia1, noticia2, noticia3]}


def test_build_vote_matrix(sample_votes):
    """Test vote matrix construction."""
    vote_matrix, voter_ids, noticia_ids = build_vote_matrix(
        time_window_days=30, min_votes_per_voter=3
    )

    # Should have 3 voters (2 users + 1 session) and 3 noticias
    assert vote_matrix.shape[0] == 3  # 3 voters
    assert vote_matrix.shape[1] == 3  # 3 noticias
    assert len(voter_ids) == 3
    assert len(noticia_ids) == 3

    # Check vote encoding (buena=1, neutral=0.0001, mala=-1)
    # User1's votes should be [1, 1, -1]
    # User2's votes should be [1, -1, -1]
    # Session1's votes should be [0.0001, 0.0001, 0.0001]
    # Note: neutral votes now use epsilon (0.0001) so they're stored in sparse matrix
    # So nnz will be 9 (all votes stored, including neutral)
    assert vote_matrix.nnz == 9  # All votes stored (including neutral with epsilon)


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
    assert pca_result["voter_projections"].shape == (n_voters, 2)
    assert pca_result["noticia_projections"].shape == (n_noticias, 2)
    assert len(pca_result["variance_explained"]) == 2
    assert len(pca_result["voter_vote_counts"]) == n_voters
    assert len(pca_result["noticia_vote_counts"]) == n_noticias
    assert all(pca_result["voter_vote_counts"] > 0)


def test_cluster_voters():
    """Test k-means clustering."""
    # Create simple 2D projections
    np.random.seed(42)
    projections = np.random.randn(20, 2)
    voter_weights = np.ones(20)

    labels, centroids, inertia = cluster_voters(projections, voter_weights, k=3)

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
        base_labels, projections, k_range=(2, 4)
    )

    # Check outputs
    assert len(group_labels) == 50
    assert 2 <= best_k <= 4
    assert len(silhouette_scores) > 0


def test_compute_cluster_consensus():
    """Test consensus score calculation."""
    # High consensus case
    cluster_votes = {
        1: {"buena": 9, "mala": 1, "neutral": 0},
        2: {"buena": 8, "mala": 2, "neutral": 0},
    }
    consensus = compute_cluster_consensus(cluster_votes)
    # Consensus = avg((9/10), (8/10)) = 0.85
    assert 0.8 <= consensus <= 0.9  # Should be high

    # Low consensus case
    cluster_votes = {
        1: {"buena": 3, "mala": 4, "neutral": 3},
        2: {"buena": 4, "mala": 3, "neutral": 3},
    }
    consensus = compute_cluster_consensus(cluster_votes)
    # Consensus = avg((4/10), (4/10)) = 0.4
    assert 0.3 <= consensus <= 0.5  # Should be low


def test_compute_voter_similarity():
    """Test voter similarity calculation."""
    # Identical votes
    voter_a = {1: "buena", 2: "buena", 3: "mala"}
    voter_b = {1: "buena", 2: "buena", 3: "mala"}
    similarity = compute_voter_similarity(voter_a, voter_b)
    assert similarity == 1.0

    # Complete disagreement
    voter_a = {1: "buena", 2: "buena", 3: "buena"}
    voter_b = {1: "mala", 2: "mala", 3: "mala"}
    similarity = compute_voter_similarity(voter_a, voter_b)
    assert similarity == 0.0

    # Partial agreement
    voter_a = {1: "buena", 2: "buena", 3: "mala"}
    voter_b = {1: "buena", 2: "mala", 3: "mala"}
    similarity = compute_voter_similarity(voter_a, voter_b)
    assert similarity == 2 / 3  # 2 out of 3 agree

    # No overlap
    voter_a = {1: "buena", 2: "buena"}
    voter_b = {3: "mala", 4: "mala"}
    similarity = compute_voter_similarity(voter_a, voter_b)
    assert similarity is None


def test_voter_cluster_run_creation(db):
    """Test VoterClusterRun model."""
    run = VoterClusterRun.objects.create(
        status="pending", parameters={"time_window_days": 30}
    )

    assert run.id is not None
    assert run.status == "pending"
    assert run.n_voters == 0
    assert run.n_clusters == 0


@pytest.mark.django_db
def test_build_vote_matrix_empty_database():
    """Test vote matrix with no votes."""
    vote_matrix, voter_ids, noticia_ids = build_vote_matrix(
        time_window_days=30, min_votes_per_voter=3
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
    projections = pca_result["voter_projections"]
    vote_counts = pca_result["voter_vote_counts"]
    labels, _, _ = cluster_voters(projections, vote_counts, k=2)

    # Map user IDs to matrix row indices
    user_index = {
        voter_id[1]: idx
        for idx, voter_id in enumerate(voter_ids)
        if voter_id[0] == "user"
    }

    label_a = labels[user_index[str(group_a[0].id)]]
    label_b = labels[user_index[str(group_b[0].id)]]

    # All A users share label_a, all B users share label_b, and they differ
    assert label_a != label_b
    for user in group_a:
        assert labels[user_index[str(user.id)]] == label_a
    for user in group_b:
        assert labels[user_index[str(user.id)]] == label_b


@pytest.mark.django_db
def test_compute_cluster_entities():
    """Test entity extraction from cluster voting patterns."""
    from core.models import (
        VoterClusterRun,
        VoterCluster,
        ClusterVotingPattern,
        Entidad,
        NoticiaEntidad,
    )

    # Create test noticias
    noticia1 = Noticia.objects.create(
        enlace="http://entity-test1.com", meta_titulo="Noticia sobre política"
    )
    noticia2 = Noticia.objects.create(
        enlace="http://entity-test2.com", meta_titulo="Noticia sobre economía"
    )

    # Create entities
    entidad_pos = Entidad.objects.create(nombre="Juan Pérez", tipo="persona")
    entidad_neg = Entidad.objects.create(nombre="Gobierno", tipo="organizacion")

    # Link entities to noticias with sentiment
    NoticiaEntidad.objects.create(
        noticia=noticia1, entidad=entidad_pos, sentimiento="positivo"
    )
    NoticiaEntidad.objects.create(
        noticia=noticia2, entidad=entidad_neg, sentimiento="negativo"
    )

    # Create a cluster run and cluster
    run = VoterClusterRun.objects.create(status="completed")
    cluster = VoterCluster.objects.create(
        run=run,
        cluster_id=0,
        cluster_type="group",
        size=10,
        centroid_x=0.0,
        centroid_y=0.0,
        consensus_score=0.8,
    )

    # Create voting patterns with high consensus
    ClusterVotingPattern.objects.create(
        cluster=cluster,
        noticia=noticia1,
        count_buena=8,
        count_mala=1,
        count_neutral=1,
        consensus_score=0.8,
        majority_opinion="buena",
    )
    ClusterVotingPattern.objects.create(
        cluster=cluster,
        noticia=noticia2,
        count_buena=1,
        count_mala=8,
        count_neutral=1,
        consensus_score=0.8,
        majority_opinion="mala",
    )

    # Test entity extraction
    entities_pos, entities_neg = compute_cluster_entities(cluster, top_n=5)

    # Should find Juan Pérez as positive (from noticia1 voted buena)
    assert len(entities_pos) == 1
    assert entities_pos[0]["nombre"] == "Juan Pérez"
    assert entities_pos[0]["tipo"] == "persona"

    # Should find Gobierno as negative (from noticia2 voted mala)
    assert len(entities_neg) == 1
    assert entities_neg[0]["nombre"] == "Gobierno"
    assert entities_neg[0]["tipo"] == "organizacion"


# ============================================================================
# Tests for Null Votes vs Neutral Votes (Polis-style handling)
# ============================================================================


@pytest.mark.django_db
def test_neutral_votes_stored_with_epsilon():
    """
    Test that neutral votes are stored with epsilon (0.0001) in sparse matrix.
    This allows distinguishing between explicit neutral votes and missing votes.
    """

    user = User.objects.create_user("testuser", "test@test.com", "pass")
    noticia = Noticia.objects.create(
        enlace="http://neutral-test.com", meta_titulo="Test Neutral"
    )

    # Create a neutral vote
    Voto.objects.create(usuario=user, noticia=noticia, opinion="neutral")

    vote_matrix, voter_ids, noticia_ids = build_vote_matrix(
        time_window_days=30, min_votes_per_voter=1
    )

    # Should have 1 voter and 1 noticia
    assert vote_matrix.shape == (1, 1)
    assert len(voter_ids) == 1
    assert len(noticia_ids) == 1

    # Neutral vote should be stored (not missing)
    assert vote_matrix.nnz == 1  # One non-zero entry (the epsilon)

    # Check that the value is epsilon (0.0001)
    NEUTRAL_EPSILON = 0.0001
    stored_value = vote_matrix[0, 0]
    assert abs(stored_value - NEUTRAL_EPSILON) < 1e-10


@pytest.mark.django_db
def test_missing_votes_not_stored_in_matrix():
    """
    Test that missing votes (participants who didn't vote) are NOT stored
    in the sparse matrix, distinguishing them from explicit neutral votes.
    """
    user1 = User.objects.create_user("user1", "user1@test.com", "pass")
    user2 = User.objects.create_user("user2", "user2@test.com", "pass")

    noticia1 = Noticia.objects.create(enlace="http://test1.com", meta_titulo="Test 1")
    noticia2 = Noticia.objects.create(enlace="http://test2.com", meta_titulo="Test 2")

    # User1 votes on both noticias
    Voto.objects.create(usuario=user1, noticia=noticia1, opinion="buena")
    Voto.objects.create(usuario=user1, noticia=noticia2, opinion="mala")

    # User2 only votes on noticia1 (missing vote on noticia2)
    Voto.objects.create(usuario=user2, noticia=noticia1, opinion="buena")
    # No vote on noticia2 - this should be missing, not stored

    vote_matrix, voter_ids, noticia_ids = build_vote_matrix(
        time_window_days=30, min_votes_per_voter=1
    )

    # Should have 2 voters and 2 noticias
    assert vote_matrix.shape == (2, 2)

    # Should have 3 stored votes (user1: 2 votes, user2: 1 vote)
    # Missing vote should NOT be stored
    assert vote_matrix.nnz == 3

    # Find indices
    user1_idx = next(
        i
        for i, (vt, vid) in enumerate(voter_ids)
        if vt == "user" and vid == str(user1.id)
    )
    user2_idx = next(
        i
        for i, (vt, vid) in enumerate(voter_ids)
        if vt == "user" and vid == str(user2.id)
    )
    noticia1_idx = noticia_ids.index(noticia1.id)
    noticia2_idx = noticia_ids.index(noticia2.id)

    # User1 should have votes on both
    assert vote_matrix[user1_idx, noticia1_idx] == 1.0  # buena
    assert vote_matrix[user1_idx, noticia2_idx] == -1.0  # mala

    # User2 should have vote on noticia1 only
    assert vote_matrix[user2_idx, noticia1_idx] == 1.0  # buena
    # User2's vote on noticia2 should be missing (0.0 after toarray, but not stored)
    # Check that it's not in the sparse structure
    vote_matrix_csr = vote_matrix.tocsr()
    column = vote_matrix_csr[:, noticia2_idx]
    row_indices = column.indices if hasattr(column, "indices") else []
    assert user2_idx not in row_indices  # Missing vote not stored


@pytest.mark.django_db
def test_aggregation_distinguishes_neutral_from_missing():
    """
    Test that compute_cluster_voting_aggregation correctly distinguishes
    between explicit neutral votes and missing votes (Polis-style).
    """
    user1 = User.objects.create_user("user1", "user1@test.com", "pass")
    user2 = User.objects.create_user("user2", "user2@test.com", "pass")
    user3 = User.objects.create_user("user3", "user3@test.com", "pass")

    noticia = Noticia.objects.create(
        enlace="http://aggregation-test.com", meta_titulo="Aggregation Test"
    )

    # User1: explicit neutral vote
    Voto.objects.create(usuario=user1, noticia=noticia, opinion="neutral")
    # User2: buena vote
    Voto.objects.create(usuario=user2, noticia=noticia, opinion="buena")
    # User3: no vote (missing) - should NOT be counted

    vote_matrix, voter_ids, noticia_ids = build_vote_matrix(
        time_window_days=30, min_votes_per_voter=1
    )

    # All 3 users should be in matrix (user3 has 0 votes but we need min_votes_per_voter=1)
    # Actually, user3 won't be included because min_votes_per_voter=1 and they have 0 votes
    # Let's give user3 a vote on another noticia so they qualify
    noticia2 = Noticia.objects.create(enlace="http://other.com", meta_titulo="Other")
    Voto.objects.create(usuario=user3, noticia=noticia2, opinion="buena")

    # Rebuild matrix
    vote_matrix, voter_ids, noticia_ids = build_vote_matrix(
        time_window_days=30, min_votes_per_voter=1
    )

    # Find indices
    user1_idx = next(
        i
        for i, (vt, vid) in enumerate(voter_ids)
        if vt == "user" and vid == str(user1.id)
    )
    user2_idx = next(
        i
        for i, (vt, vid) in enumerate(voter_ids)
        if vt == "user" and vid == str(user2.id)
    )
    user3_idx = next(
        i
        for i, (vt, vid) in enumerate(voter_ids)
        if vt == "user" and vid == str(user3.id)
    )

    noticia_idx = noticia_ids.index(noticia.id)

    # Aggregate votes for all 3 users on this noticia
    cluster_members = np.array([user1_idx, user2_idx, user3_idx])
    aggregation = compute_cluster_voting_aggregation(
        cluster_members, voter_ids, vote_matrix, noticia_ids
    )

    # Should have aggregation for this noticia
    assert noticia.id in aggregation

    agg = aggregation[noticia.id]

    # Should count: 1 neutral (user1), 1 buena (user2), 0 mala
    # User3's missing vote should NOT be counted
    assert agg["neutral"] == 1, f"Expected 1 neutral vote, got {agg['neutral']}"
    assert agg["buena"] == 1, f"Expected 1 buena vote, got {agg['buena']}"
    assert agg["mala"] == 0, f"Expected 0 mala votes, got {agg['mala']}"
    assert agg["total"] == 2, f"Expected 2 total votes, got {agg['total']}"


@pytest.mark.django_db
def test_aggregation_only_counts_explicit_votes():
    """
    Test that aggregation only counts explicit votes, not missing ones.
    This is the core Polis behavior: missing votes are not counted as neutral.
    """
    # Create 5 users
    users = [
        User.objects.create_user(f"user{i}", f"user{i}@test.com", "pass")
        for i in range(5)
    ]

    noticia = Noticia.objects.create(
        enlace="http://explicit-test.com", meta_titulo="Explicit Votes Test"
    )

    # User0: buena
    Voto.objects.create(usuario=users[0], noticia=noticia, opinion="buena")
    # User1: mala
    Voto.objects.create(usuario=users[1], noticia=noticia, opinion="mala")
    # User2: neutral
    Voto.objects.create(usuario=users[2], noticia=noticia, opinion="neutral")
    # User3: no vote (missing)
    # User4: no vote (missing)

    # Give users 3 and 4 votes on other noticias so they qualify
    noticia_other = Noticia.objects.create(
        enlace="http://other.com", meta_titulo="Other"
    )
    Voto.objects.create(usuario=users[3], noticia=noticia_other, opinion="buena")
    Voto.objects.create(usuario=users[4], noticia=noticia_other, opinion="buena")

    vote_matrix, voter_ids, noticia_ids = build_vote_matrix(
        time_window_days=30, min_votes_per_voter=1
    )

    # All 5 users should be in matrix
    assert vote_matrix.shape[0] == 5

    # Find indices
    user_indices = [
        next(
            i
            for i, (vt, vid) in enumerate(voter_ids)
            if vt == "user" and vid == str(user.id)
        )
        for user in users
    ]

    noticia_idx = noticia_ids.index(noticia.id)

    # Aggregate all users
    cluster_members = np.array(user_indices)
    aggregation = compute_cluster_voting_aggregation(
        cluster_members, voter_ids, vote_matrix, noticia_ids
    )

    agg = aggregation[noticia.id]

    # Should only count 3 explicit votes (buena, mala, neutral)
    # Missing votes from users 3 and 4 should NOT be counted
    assert agg["buena"] == 1
    assert agg["mala"] == 1
    assert agg["neutral"] == 1
    assert agg["total"] == 3  # Only 3 explicit votes, not 5


@pytest.mark.django_db
def test_pca_handles_epsilon_correctly():
    """
    Test that PCA correctly handles epsilon values for neutral votes,
    converting them back to 0.0 for mean-centering.
    """
    user1 = User.objects.create_user("user1", "user1@test.com", "pass")
    user2 = User.objects.create_user("user2", "user2@test.com", "pass")

    noticia1 = Noticia.objects.create(
        enlace="http://pca-test1.com", meta_titulo="PCA Test 1"
    )
    noticia2 = Noticia.objects.create(
        enlace="http://pca-test2.com", meta_titulo="PCA Test 2"
    )

    # Mix of votes including neutral
    Voto.objects.create(usuario=user1, noticia=noticia1, opinion="buena")
    Voto.objects.create(usuario=user1, noticia=noticia2, opinion="neutral")
    Voto.objects.create(usuario=user2, noticia=noticia1, opinion="mala")
    Voto.objects.create(usuario=user2, noticia=noticia2, opinion="buena")

    vote_matrix, voter_ids, noticia_ids = build_vote_matrix(
        time_window_days=30, min_votes_per_voter=2
    )

    # PCA should handle this without errors
    pca_result = compute_sparsity_aware_pca(vote_matrix, n_components=2)

    # Check outputs
    assert pca_result["voter_projections"].shape == (2, 2)
    assert pca_result["noticia_projections"].shape == (2, 2)
    assert len(pca_result["variance_explained"]) == 2

    # Vote counts should be correct (both users voted on both noticias)
    assert all(pca_result["voter_vote_counts"] == 2)
    assert all(pca_result["noticia_vote_counts"] == 2)


@pytest.mark.django_db
def test_integration_neutral_vs_missing_complete_flow():
    """
    Integration test: Complete flow from votes to aggregation,
    verifying that neutral and missing votes are handled correctly throughout.
    """
    # Create scenario:
    # - 3 noticias
    # - 4 users with different voting patterns
    # - Some explicit neutral votes, some missing votes

    users = [
        User.objects.create_user(f"user{i}", f"user{i}@test.com", "pass")
        for i in range(4)
    ]

    noticias = [
        Noticia.objects.create(
            enlace=f"http://integration-test{i}.com",
            meta_titulo=f"Integration Test {i}",
        )
        for i in range(3)
    ]

    # User0: votes on all 3 (buena, neutral, mala)
    Voto.objects.create(usuario=users[0], noticia=noticias[0], opinion="buena")
    Voto.objects.create(usuario=users[0], noticia=noticias[1], opinion="neutral")
    Voto.objects.create(usuario=users[0], noticia=noticias[2], opinion="mala")

    # User1: votes on 2 (buena, buena), missing on noticia2
    Voto.objects.create(usuario=users[1], noticia=noticias[0], opinion="buena")
    Voto.objects.create(usuario=users[1], noticia=noticias[1], opinion="buena")
    # Missing on noticias[2]

    # User2: votes on 1 (neutral), missing on others
    Voto.objects.create(usuario=users[2], noticia=noticias[0], opinion="neutral")
    # Missing on noticias[1] and noticias[2]

    # User3: votes on 1 (mala), missing on others
    Voto.objects.create(usuario=users[3], noticia=noticias[0], opinion="mala")
    # Missing on noticias[1] and noticias[2]

    # Build matrix
    vote_matrix, voter_ids, noticia_ids = build_vote_matrix(
        time_window_days=30, min_votes_per_voter=1
    )

    # All 4 users should be included (all have at least 1 vote)
    assert vote_matrix.shape[0] == 4
    assert vote_matrix.shape[1] == 3

    # Find indices
    user_indices = [
        next(
            i
            for i, (vt, vid) in enumerate(voter_ids)
            if vt == "user" and vid == str(user.id)
        )
        for user in users
    ]

    # Aggregate for noticia0 (all users voted)
    noticia0_idx = noticia_ids.index(noticias[0].id)
    cluster_members = np.array(user_indices)
    aggregation = compute_cluster_voting_aggregation(
        cluster_members, voter_ids, vote_matrix, noticia_ids
    )

    agg0 = aggregation[noticias[0].id]
    # User0: buena, User1: buena, User2: neutral, User3: mala
    assert agg0["buena"] == 2
    assert agg0["neutral"] == 1
    assert agg0["mala"] == 1
    assert agg0["total"] == 4

    # Aggregate for noticia1 (only users 0 and 1 voted)
    agg1 = aggregation[noticias[1].id]
    # User0: neutral, User1: buena
    # Users 2 and 3 missing - should NOT be counted
    assert agg1["buena"] == 1
    assert agg1["neutral"] == 1
    assert agg1["mala"] == 0
    assert agg1["total"] == 2  # Only 2 explicit votes, not 4

    # Aggregate for noticia2 (only user0 voted)
    agg2 = aggregation[noticias[2].id]
    # User0: mala
    # Users 1, 2, 3 missing - should NOT be counted
    assert agg2["buena"] == 0
    assert agg2["neutral"] == 0
    assert agg2["mala"] == 1
    assert agg2["total"] == 1  # Only 1 explicit vote, not 4


@pytest.mark.django_db
def test_aggregation_with_shared_noticias():
    """
    Test that aggregation works when cluster members vote on the same noticias.
    This is a regression test for the bug where clusters have members but no voting patterns.
    """
    # Create 5 users who all vote on the same 3 noticias
    users = [
        User.objects.create_user(f"user{i}", f"user{i}@test.com", "pass")
        for i in range(5)
    ]

    # Create 3 noticias that all users will vote on
    noticias = [
        Noticia.objects.create(
            enlace=f"http://shared-test{i}.com", meta_titulo=f"Shared Test {i}"
        )
        for i in range(3)
    ]

    # All users vote on all 3 noticias with different patterns
    # User0: buena, buena, buena
    # User1: buena, mala, neutral
    # User2: mala, mala, buena
    # User3: neutral, buena, mala
    # User4: buena, neutral, neutral

    patterns = [
        ["buena", "buena", "buena"],
        ["buena", "mala", "neutral"],
        ["mala", "mala", "buena"],
        ["neutral", "buena", "mala"],
        ["buena", "neutral", "neutral"],
    ]

    for user, pattern in zip(users, patterns):
        for noticia, opinion in zip(noticias, pattern):
            Voto.objects.create(usuario=user, noticia=noticia, opinion=opinion)

    # Build matrix
    vote_matrix, voter_ids, noticia_ids = build_vote_matrix(
        time_window_days=30, min_votes_per_voter=3
    )

    # All 5 users should be in matrix (all have 3 votes)
    assert vote_matrix.shape[0] == 5
    assert vote_matrix.shape[1] == 3

    # All 3 noticias should be in matrix
    assert len(noticia_ids) == 3
    assert all(n.id in noticia_ids for n in noticias)

    # Find user indices
    user_indices = [
        next(
            i
            for i, (vt, vid) in enumerate(voter_ids)
            if vt == "user" and vid == str(user.id)
        )
        for user in users
    ]

    # Aggregate all users (they form a cluster)
    cluster_members = np.array(user_indices)
    aggregation = compute_cluster_voting_aggregation(
        cluster_members, voter_ids, vote_matrix, noticia_ids
    )

    # Should have aggregation for all 3 noticias
    assert len(aggregation) == 3

    # Check noticia0: buena=3, mala=1, neutral=1
    agg0 = aggregation[noticias[0].id]
    assert agg0["buena"] == 3
    assert agg0["mala"] == 1
    assert agg0["neutral"] == 1
    assert agg0["total"] == 5

    # Check noticia1: buena=2, mala=2, neutral=1
    agg1 = aggregation[noticias[1].id]
    assert agg1["buena"] == 2
    assert agg1["mala"] == 2
    assert agg1["neutral"] == 1
    assert agg1["total"] == 5

    # Check noticia2: buena=2, mala=1, neutral=2
    agg2 = aggregation[noticias[2].id]
    assert agg2["buena"] == 2
    assert agg2["mala"] == 1
    assert agg2["neutral"] == 2
    assert agg2["total"] == 5


# ============================================================================
# Tests for ClusterNameCache (LLM name caching with TTL)
# ============================================================================


@pytest.mark.django_db
def test_cluster_name_cache_model():
    """Test ClusterNameCache model creation and is_expired method."""
    from core.models import ClusterNameCache
    from django.utils import timezone
    from datetime import timedelta

    # Create a cache entry that expires in the future
    future_expiry = timezone.now() + timedelta(days=7)
    cache = ClusterNameCache.objects.create(
        content_hash="abc123",
        name="Los Escépticos",
        description="Grupo crítico del gobierno",
        noticia_ids=[1, 2, 3],
        entities_positive=[{"nombre": "Juan", "tipo": "persona"}],
        entities_negative=[{"nombre": "Gobierno", "tipo": "organizacion"}],
        expires_at=future_expiry,
    )

    assert cache.id is not None
    assert cache.name == "Los Escépticos"
    assert cache.use_count == 1
    assert not cache.is_expired()

    # Create an expired cache entry
    past_expiry = timezone.now() - timedelta(days=1)
    expired_cache = ClusterNameCache.objects.create(
        content_hash="def456",
        name="Los Optimistas",
        description="Grupo positivo",
        noticia_ids=[4, 5],
        entities_positive=[],
        entities_negative=[],
        expires_at=past_expiry,
    )

    assert expired_cache.is_expired()


@pytest.mark.django_db
def test_compute_cluster_content_hash():
    """Test content hash computation is deterministic and order-independent."""
    from core.tasks import compute_cluster_content_hash

    entities_pos = [
        {"nombre": "Juan", "tipo": "persona"},
        {"nombre": "Maria", "tipo": "persona"},
    ]
    entities_neg = [{"nombre": "Gobierno", "tipo": "organizacion"}]

    hash1 = compute_cluster_content_hash([1, 2, 3], entities_pos, entities_neg)
    hash2 = compute_cluster_content_hash([1, 2, 3], entities_pos, entities_neg)

    # Same inputs should produce same hash
    assert hash1 == hash2

    # Order of noticia_ids shouldn't matter (they get sorted)
    hash3 = compute_cluster_content_hash([3, 1, 2], entities_pos, entities_neg)
    assert hash1 == hash3

    # Order of entities shouldn't matter (names get sorted)
    entities_pos_reversed = [
        {"nombre": "Maria", "tipo": "persona"},
        {"nombre": "Juan", "tipo": "persona"},
    ]
    hash4 = compute_cluster_content_hash([1, 2, 3], entities_pos_reversed, entities_neg)
    assert hash1 == hash4

    # Different inputs should produce different hash
    hash5 = compute_cluster_content_hash([1, 2, 4], entities_pos, entities_neg)
    assert hash1 != hash5


@pytest.mark.django_db
def test_get_or_create_cluster_name_cache_hit():
    """Test that cache hit returns cached name without calling LLM."""
    from unittest.mock import patch
    from core.models import ClusterNameCache
    from core.tasks import get_or_create_cluster_name, compute_cluster_content_hash
    from django.utils import timezone
    from datetime import timedelta

    # Create noticias for the test
    noticia1 = Noticia.objects.create(
        enlace="http://cache-test1.com", meta_titulo="Cache Test 1"
    )
    noticia2 = Noticia.objects.create(
        enlace="http://cache-test2.com", meta_titulo="Cache Test 2"
    )

    noticia_ids = [noticia1.id, noticia2.id]
    entities_pos = [{"nombre": "Juan", "tipo": "persona"}]
    entities_neg = [{"nombre": "Gobierno", "tipo": "organizacion"}]

    # Pre-populate cache
    content_hash = compute_cluster_content_hash(noticia_ids, entities_pos, entities_neg)
    ClusterNameCache.objects.create(
        content_hash=content_hash,
        name="Cached Name",
        description="Cached description",
        noticia_ids=sorted(noticia_ids),
        entities_positive=entities_pos,
        entities_negative=entities_neg,
        expires_at=timezone.now() + timedelta(days=7),
        use_count=1,
    )

    # Mock the LLM call to ensure it's not called
    with patch("core.tasks.parse.generate_cluster_description") as mock_generate:
        name, description, from_cache = get_or_create_cluster_name(
            noticia_ids=noticia_ids,
            entities_pos=entities_pos,
            entities_neg=entities_neg,
            cluster_size=10,
            consensus_score=0.8,
        )

        assert name == "Cached Name"
        assert description == "Cached description"
        assert from_cache is True
        mock_generate.assert_not_called()

    # Check use_count was incremented
    cache = ClusterNameCache.objects.get(content_hash=content_hash)
    assert cache.use_count == 2


@pytest.mark.django_db
def test_get_or_create_cluster_name_cache_miss():
    """Test that cache miss calls LLM and stores result."""
    from unittest.mock import patch
    from core.models import ClusterNameCache
    from core.tasks import get_or_create_cluster_name, compute_cluster_content_hash
    from core.parse import ClusterDescription

    # Create noticias
    noticia1 = Noticia.objects.create(
        enlace="http://miss-test1.com", meta_titulo="Miss Test 1"
    )
    noticia2 = Noticia.objects.create(
        enlace="http://miss-test2.com", meta_titulo="Miss Test 2"
    )

    noticia_ids = [noticia1.id, noticia2.id]
    entities_pos = [{"nombre": "Pedro", "tipo": "persona"}]
    entities_neg = []

    # Mock LLM to return a description
    mock_description = ClusterDescription(
        nombre="Generated Name", descripcion="Generated description"
    )
    with patch(
        "core.tasks.parse.generate_cluster_description", return_value=mock_description
    ):
        name, description, from_cache = get_or_create_cluster_name(
            noticia_ids=noticia_ids,
            entities_pos=entities_pos,
            entities_neg=entities_neg,
            cluster_size=5,
            consensus_score=0.7,
        )

    assert name == "Generated Name"
    assert description == "Generated description"
    assert from_cache is False

    # Check cache was created
    content_hash = compute_cluster_content_hash(noticia_ids, entities_pos, entities_neg)
    cache = ClusterNameCache.objects.get(content_hash=content_hash)
    assert cache.name == "Generated Name"
    assert cache.use_count == 1


@pytest.mark.django_db
def test_get_or_create_cluster_name_expired_cache():
    """Test that expired cache triggers LLM regeneration."""
    from unittest.mock import patch
    from core.models import ClusterNameCache
    from core.tasks import get_or_create_cluster_name, compute_cluster_content_hash
    from core.parse import ClusterDescription
    from django.utils import timezone
    from datetime import timedelta

    # Create noticias
    noticia1 = Noticia.objects.create(
        enlace="http://expired-test1.com", meta_titulo="Expired Test 1"
    )

    noticia_ids = [noticia1.id]
    entities_pos = []
    entities_neg = []

    # Create expired cache entry
    content_hash = compute_cluster_content_hash(noticia_ids, entities_pos, entities_neg)
    ClusterNameCache.objects.create(
        content_hash=content_hash,
        name="Old Expired Name",
        description="Old description",
        noticia_ids=sorted(noticia_ids),
        entities_positive=entities_pos,
        entities_negative=entities_neg,
        expires_at=timezone.now() - timedelta(days=1),  # Expired yesterday
        use_count=5,
    )

    # Mock LLM
    mock_description = ClusterDescription(
        nombre="Refreshed Name", descripcion="Refreshed description"
    )
    with patch(
        "core.tasks.parse.generate_cluster_description", return_value=mock_description
    ):
        name, description, from_cache = get_or_create_cluster_name(
            noticia_ids=noticia_ids,
            entities_pos=entities_pos,
            entities_neg=entities_neg,
            cluster_size=3,
            consensus_score=0.6,
        )

    assert name == "Refreshed Name"
    assert description == "Refreshed description"
    assert from_cache is False

    # Check cache was updated (not duplicated)
    assert ClusterNameCache.objects.filter(content_hash=content_hash).count() == 1
    cache = ClusterNameCache.objects.get(content_hash=content_hash)
    assert cache.name == "Refreshed Name"
    assert cache.use_count == 1  # Reset on refresh


@pytest.mark.django_db
def test_get_or_create_cluster_name_llm_failure():
    """Test graceful handling when LLM fails."""
    from unittest.mock import patch
    from core.models import ClusterNameCache
    from core.tasks import get_or_create_cluster_name

    noticia1 = Noticia.objects.create(
        enlace="http://fail-test.com", meta_titulo="Fail Test"
    )

    # Mock LLM to return None (failure)
    with patch("core.tasks.parse.generate_cluster_description", return_value=None):
        name, description, from_cache = get_or_create_cluster_name(
            noticia_ids=[noticia1.id],
            entities_pos=[],
            entities_neg=[],
            cluster_size=2,
            consensus_score=0.5,
        )

    assert name is None
    assert description is None
    assert from_cache is False

    # No cache entry should be created on failure
    assert ClusterNameCache.objects.count() == 0
