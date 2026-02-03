"""
Unit tests for timeline feed algorithms (core.feeds).

Tests are isolated: they use the feed functions directly with minimal DB setup,
no request/response.
"""

import pytest
from django.contrib.auth import get_user_model

from core.models import (
    Noticia,
    Voto,
    Entidad,
    NoticiaEntidad,
    VoterClusterRun,
    VoterCluster,
    VoterClusterMembership,
    ClusterVotingPattern,
)
from core.feeds import (
    FEED_RECIENTES,
    FEED_CONFORT,
    FEED_PUENTE,
    FEED_AVANZADO,
    DEFAULT_FEED,
    COMFORT_CLUSTER_CONSENSUS_MIN,
    filter_recientes,
    get_confort_noticia_ids,
    get_puente_ordered_noticia_ids,
)

User = get_user_model()


# ---- filter_recientes ----


@pytest.mark.django_db
class TestFilterRecientes:
    """Tests for recientes feed: exclude voted noticias."""

    def test_excludes_voted_by_user(self):
        user = User.objects.create_user(username="u1", email="u1@test.com")
        n1 = Noticia.objects.create(enlace="https://a.com/1", meta_titulo="N1")
        n2 = Noticia.objects.create(enlace="https://a.com/2", meta_titulo="N2")
        Voto.objects.create(usuario=user, noticia=n1, opinion="buena")
        qs = Noticia.objects.all().order_by("id")
        result = filter_recientes(qs, user=user, session_key=None)
        ids = list(result.values_list("id", flat=True))
        assert n2.id in ids
        assert n1.id not in ids

    def test_excludes_voted_by_session(self):
        sk = "session-abc"
        n1 = Noticia.objects.create(enlace="https://b.com/1", meta_titulo="N1")
        n2 = Noticia.objects.create(enlace="https://b.com/2", meta_titulo="N2")
        Voto.objects.create(session_key=sk, noticia=n1, opinion="mala")
        qs = Noticia.objects.all().order_by("id")
        result = filter_recientes(qs, user=None, session_key=sk)
        ids = list(result.values_list("id", flat=True))
        assert n2.id in ids
        assert n1.id not in ids

    def test_no_user_no_session_returns_unchanged(self):
        Noticia.objects.create(enlace="https://c.com/1", meta_titulo="N1")
        qs = Noticia.objects.all()
        result = filter_recientes(qs, user=None, session_key=None)
        assert result.count() == 1

    def test_empty_queryset(self):
        user = User.objects.create_user(username="u2", email="u2@test.com")
        qs = Noticia.objects.none()
        result = filter_recientes(qs, user=user, session_key=None)
        assert list(result) == []


# ---- get_confort_noticia_ids ----


@pytest.mark.django_db
class TestGetConfortNoticiaIds:
    """Tests for comfort (afín) feed algorithm."""

    def test_returns_none_when_no_voter_id(self):
        assert get_confort_noticia_ids("user", "", {"usuario_id": 1}) is None
        assert get_confort_noticia_ids("session", "", {"session_key": "x"}) is None

    def test_returns_none_when_no_cluster_run(self, user):
        lookup = {"usuario": user}
        result = get_confort_noticia_ids("user", str(user.id), lookup)
        assert result is None

    def test_returns_none_when_no_membership(self, user):
        VoterClusterRun.objects.create(
            status="completed", n_voters=1, n_noticias=0, n_clusters=0
        )
        lookup = {"usuario": user}
        result = get_confort_noticia_ids("user", str(user.id), lookup)
        assert result is None

    def test_includes_cluster_positive_noticias(self, user, cluster_run_with_members):
        run, cluster, _ = cluster_run_with_members
        n1 = Noticia.objects.create(enlace="https://d.com/1", meta_titulo="N1")
        ClusterVotingPattern.objects.create(
            cluster=cluster,
            noticia=n1,
            count_buena=8,
            count_mala=1,
            count_neutral=1,
            consensus_score=0.8,
            majority_opinion="buena",
        )
        lookup = {"usuario": user}
        result = get_confort_noticia_ids("user", str(user.id), lookup)
        assert result is not None
        assert n1.id in result

    def test_excludes_low_consensus_cluster_noticias(self, user, cluster_run_with_members):
        run, cluster, _ = cluster_run_with_members
        n_high = Noticia.objects.create(enlace="https://e.com/high", meta_titulo="High")
        n_low = Noticia.objects.create(enlace="https://e.com/low", meta_titulo="Low")
        ClusterVotingPattern.objects.create(
            cluster=cluster,
            noticia=n_high,
            count_buena=9,
            count_mala=0,
            count_neutral=1,
            consensus_score=0.9,
            majority_opinion="buena",
        )
        ClusterVotingPattern.objects.create(
            cluster=cluster,
            noticia=n_low,
            count_buena=5,
            count_mala=5,
            count_neutral=0,
            consensus_score=0.5,
            majority_opinion="buena",
        )
        lookup = {"usuario": user}
        result = get_confort_noticia_ids(
            "user", str(user.id), lookup, cluster_consensus_min=0.6
        )
        assert result is not None
        assert n_high.id in result
        assert n_low.id not in result

    def test_includes_peers_buena_noticias(self, user, cluster_run_with_members):
        run, cluster, other_user = cluster_run_with_members
        n_peer = Noticia.objects.create(enlace="https://f.com/peer", meta_titulo="Peer")
        Voto.objects.create(usuario=other_user, noticia=n_peer, opinion="buena")
        lookup = {"usuario": user}
        result = get_confort_noticia_ids("user", str(user.id), lookup)
        assert result is not None
        assert n_peer.id in result

    def test_includes_entity_positive_noticias(self, user, cluster_run_with_members):
        run, cluster, _ = cluster_run_with_members
        ent = Entidad.objects.create(nombre="Test Entity", tipo="persona")
        n_voted = Noticia.objects.create(enlace="https://g.com/v", meta_titulo="Voted")
        n_about = Noticia.objects.create(enlace="https://g.com/about", meta_titulo="About")
        Voto.objects.create(usuario=user, noticia=n_voted, opinion="buena")
        NoticiaEntidad.objects.create(noticia=n_voted, entidad=ent, sentimiento="positivo")
        NoticiaEntidad.objects.create(noticia=n_about, entidad=ent, sentimiento="positivo")
        lookup = {"usuario": user}
        result = get_confort_noticia_ids("user", str(user.id), lookup)
        assert result is not None
        assert n_about.id in result

    def test_returns_none_when_membership_but_no_candidates(self, user, cluster_run_with_members):
        run, cluster, _ = cluster_run_with_members
        # No ClusterVotingPattern "buena", no peers votes, no entity links
        lookup = {"usuario": user}
        result = get_confort_noticia_ids("user", str(user.id), lookup)
        assert result is None


@pytest.fixture
def user(db):
    return User.objects.create_user(username="feeduser", email="feed@test.com")


@pytest.fixture
def cluster_run_with_members(db, user):
    """Cluster run with one cluster and two members (user + other_user)."""
    other_user = User.objects.create_user(username="other", email="other@test.com")
    run = VoterClusterRun.objects.create(
        status="completed",
        n_voters=2,
        n_noticias=0,
        n_clusters=1,
    )
    cluster = VoterCluster.objects.create(
        run=run,
        cluster_id=1,
        cluster_type="group",
        size=2,
        centroid_x=0.0,
        centroid_y=0.0,
    )
    VoterClusterMembership.objects.create(
        cluster=cluster, voter_type="user", voter_id=str(user.id)
    )
    VoterClusterMembership.objects.create(
        cluster=cluster, voter_type="user", voter_id=str(other_user.id)
    )
    return run, cluster, other_user


# ---- get_puente_ordered_noticia_ids ----


@pytest.mark.django_db
class TestGetPuenteOrderedNoticiaIds:
    """Tests for puente (bridge) feed algorithm."""

    def test_returns_empty_when_no_cluster_run(self):
        result = get_puente_ordered_noticia_ids({"usuario_id": 999})
        assert result == []

    def test_returns_empty_when_no_consensus_data(self):
        """With one cluster, consensus module returns [] (needs 2+ clusters)."""
        run = VoterClusterRun.objects.create(
            status="completed",
            n_voters=1,
            n_noticias=0,
            n_clusters=1,
        )
        result = get_puente_ordered_noticia_ids({})
        assert result == []

    def test_returns_list_type(self):
        result = get_puente_ordered_noticia_ids({})
        assert isinstance(result, list)

    def test_excludes_voted_from_consensus_list(self, puente_two_cluster_run):
        """When voter has voted on a noticia in consensus list, it is excluded from result."""
        run, noticia1, noticia2, voter = puente_two_cluster_run
        # Voter votes on noticia1; consensus list might include both
        Voto.objects.create(usuario=voter, noticia=noticia1, opinion="buena")
        lookup = {"usuario": voter}
        result = get_puente_ordered_noticia_ids(lookup)
        assert noticia1.id not in result
        # noticia2 might be in result (depending on consensus)
        assert isinstance(result, list)


@pytest.fixture
def puente_two_cluster_run(db):
    """
    Run with 2 group clusters and shared votes so calculate_consensus_news can return data.
    Consensus needs >= 2 clusters with min_votes_per_cluster each.
    """
    from core.clustering.consensus import calculate_consensus_news

    u1 = User.objects.create_user(username="puente_u1", email="p1@test.com")
    u2 = User.objects.create_user(username="puente_u2", email="p2@test.com")
    voter = User.objects.create_user(username="puente_voter", email="v@test.com")
    noticia1 = Noticia.objects.create(enlace="https://puente.com/1", meta_titulo="P1")
    noticia2 = Noticia.objects.create(enlace="https://puente.com/2", meta_titulo="P2")
    for u in (u1, u2):
        Voto.objects.create(usuario=u, noticia=noticia1, opinion="buena")
        Voto.objects.create(usuario=u, noticia=noticia2, opinion="buena")
    run = VoterClusterRun.objects.create(
        status="completed",
        n_voters=3,
        n_noticias=2,
        n_clusters=2,
    )
    c1 = VoterCluster.objects.create(
        run=run, cluster_id=1, cluster_type="group", size=1, centroid_x=0.0, centroid_y=0.0
    )
    c2 = VoterCluster.objects.create(
        run=run, cluster_id=2, cluster_type="group", size=1, centroid_x=1.0, centroid_y=1.0
    )
    VoterClusterMembership.objects.create(cluster=c1, voter_type="user", voter_id=str(u1.id))
    VoterClusterMembership.objects.create(cluster=c2, voter_type="user", voter_id=str(u2.id))
    consensus = calculate_consensus_news(
        run, min_votes_per_cluster=1, consensus_threshold=0.5, top_n=10
    )
    if not consensus:
        return run, noticia1, noticia2, voter
    return run, noticia1, noticia2, voter


# ---- Constants ----


class TestFeedConstants:
    """Feed mode constants are stable."""

    def test_feed_names(self):
        assert FEED_RECIENTES == "recientes"
        assert FEED_CONFORT == "confort"
        assert FEED_PUENTE == "puente"
        assert FEED_AVANZADO == "avanzado"
        assert DEFAULT_FEED == FEED_RECIENTES

    def test_comfort_threshold(self):
        assert 0 <= COMFORT_CLUSTER_CONSENSUS_MIN <= 1
