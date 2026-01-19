# models.py

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from core import parse
import logging

logger = logging.getLogger(__name__)


class Noticia(models.Model):
    """
    A news article submitted by a user (or anonymously).
    Stores the original URL and metadata extracted from meta tags.
    """
    enlace = models.URLField(max_length=2000, unique=True, help_text="Original news article URL")

    # SEO-friendly slug for URLs
    slug = models.SlugField(
        max_length=255,
        unique=True,
        blank=True,
        null=True,
        help_text="SEO-friendly URL slug"
    )

    # Metadata extracted from og: / twitter: tags
    meta_titulo = models.CharField(max_length=255, blank=True, null=True)
    meta_imagen = models.URLField(max_length=500, blank=True, null=True)
    meta_descripcion = models.TextField(blank=True, null=True)

    # HTML captured from browser extension (bypasses paywalls)
    captured_html = models.TextField(
        blank=True,
        null=True,
        help_text="Full HTML captured from user's browser"
    )

    fecha_agregado = models.DateTimeField(auto_now_add=True)

    # Optional: Who submitted this (can be anonymous)
    agregado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User who submitted (null if anonymous)"
    )

    def __str__(self):
        return self.meta_titulo or self.enlace

    def save(self, *args, **kwargs):
        """Auto-generate slug from title if not provided."""
        if not self.slug:
            base_slug = slugify(self.meta_titulo or f"noticia-{self.pk or ''}")
            slug = base_slug
            counter = 1
            while Noticia.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        """Return the canonical URL for this noticia."""
        from django.urls import reverse
        return reverse('noticia-detail', kwargs={'slug': self.slug})

    @property
    def mostrar_titulo(self):
        """Display title with fallback chain."""
        return self.meta_titulo or self.enlace

    @property
    def mostrar_imagen(self):
        """Display image, filtering out generic logos."""
        if self.meta_imagen and "meta/la-diaria-1000x1000" not in self.meta_imagen:
            return self.meta_imagen
        return None

    @property
    def mostrar_fecha(self):
        """Display date (just submission date for MVP)."""
        return self.fecha_agregado

    def update_meta_from_url(self):
        """
        Fetch title, image, and description from original URL meta tags.
        Fast, synchronous operation (just HTTP HEAD + parse <meta> tags).
        """
        title, image, description = parse.parse_from_meta_tags(self.enlace)
        if title:
            self.meta_titulo = title
        if image:
            self.meta_imagen = image
        if description:
            self.meta_descripcion = description
        self.save()


class Voto(models.Model):
    """
    User vote on a news article.
    Can be anonymous (session-based) or authenticated (user account).
    """
    # Either usuario OR session_key must be set (not both, not neither)
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Authenticated user (null if anonymous)"
    )
    session_key = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        db_index=True,
        help_text="Session ID for anonymous votes"
    )

    noticia = models.ForeignKey(Noticia, on_delete=models.CASCADE, related_name="votos")
    opinion = models.CharField(
        max_length=10,
        choices=[
            ("buena", "Buena noticia"),
            ("mala", "Mala noticia"),
            ("neutral", "Neutral"),
        ],
    )
    fecha_voto = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # One vote per user per article (if authenticated)
            models.UniqueConstraint(
                fields=['usuario', 'noticia'],
                condition=models.Q(usuario__isnull=False),
                name='unique_user_vote'
            ),
            # One vote per session per article (if anonymous)
            models.UniqueConstraint(
                fields=['session_key', 'noticia'],
                condition=models.Q(session_key__isnull=False),
                name='unique_session_vote'
            )
        ]

    def __str__(self):
        voter = self.usuario.username if self.usuario else f"Anon-{self.session_key[:8]}"
        return f"{voter} - {self.opinion} - {self.noticia}"

    @property
    def is_anonymous(self):
        """Check if this is an anonymous vote."""
        return self.usuario is None

    def clean(self):
        """Validate that either usuario or session_key is set, not both."""
        if not self.usuario and not self.session_key:
            raise ValidationError("Vote must have either usuario or session_key")
        if self.usuario and self.session_key:
            raise ValidationError(
                "Vote cannot have both usuario and session_key"
            )

    @classmethod
    def claim_session_votes(cls, user, session_key):
        """
        Transfer all votes from a session to a user account.
        Used when a user creates an account and wants to claim
        their past anonymous votes.

        Args:
            user: Django User object
            session_key: Session ID to claim votes from

        Returns:
            int: Number of votes claimed

        Raises:
            ValidationError: If user already has votes on same articles
        """
        from django.db import transaction

        # Find all votes for this session
        session_votes = cls.objects.filter(session_key=session_key)

        if not session_votes.exists():
            return 0

        # Check for conflicts (user already voted on same article)
        session_noticias = session_votes.values_list("noticia_id", flat=True)
        user_votes = cls.objects.filter(
            usuario=user, noticia_id__in=session_noticias
        )

        if user_votes.exists():
            conflicting = user_votes.values_list("noticia__enlace", flat=True)
            raise ValidationError(
                f"User already has votes on {len(conflicting)} articles "
                f"from this session. Cannot claim votes."
            )

        # Transfer votes atomically
        with transaction.atomic():
            count = session_votes.update(usuario=user, session_key=None)

        return count


def normalize_entity_name(name: str) -> str:
    """
    Normalize entity name for deduplication.
    - Lowercase
    - Remove accents/diacritics
    - Strip whitespace
    """
    import unicodedata
    # Normalize unicode, decompose accents, remove combining chars
    nfkd = unicodedata.normalize('NFKD', name)
    ascii_name = ''.join(c for c in nfkd if not unicodedata.combining(c))
    return ascii_name.lower().strip()


class Entidad(models.Model):
    """
    Named entity extracted from news (person, organization, location, etc.)
    Currently unused in MVP (requires LLM enrichment).
    """
    nombre = models.CharField(max_length=255)
    normalized_name = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text="Normalized name for deduplication (lowercase, no accents)"
    )
    tipo = models.CharField(
        max_length=100,
        choices=[
            ("persona", "Persona"),
            ("organizacion", "Organización"),
            ("lugar", "Lugar"),
            ("otro", "Otro"),
        ],
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['normalized_name', 'tipo'],
                name='unique_normalized_entity'
            )
        ]

    def save(self, *args, **kwargs):
        self.normalized_name = normalize_entity_name(self.nombre)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class NoticiaEntidad(models.Model):
    """
    Link between a news article and an entity, with sentiment.
    Currently unused in MVP (requires LLM enrichment).
    """
    noticia = models.ForeignKey(
        Noticia, on_delete=models.CASCADE, related_name="entidades"
    )
    entidad = models.ForeignKey(Entidad, on_delete=models.CASCADE)
    sentimiento = models.CharField(
        max_length=10,
        choices=[
            ("positivo", "Positivo"),
            ("negativo", "Negativo"),
            ("neutral", "Neutral"),
        ],
    )

    class Meta:
        unique_together = ("noticia", "entidad")

    def __str__(self):
        return f"{self.noticia} - {self.entidad.nombre}"


class VoterClusterRun(models.Model):
    """
    Track clustering computation runs (Polis-style).
    Each run represents a complete clustering computation at a point in time.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("running", "Running"),
            ("completed", "Completed"),
            ("failed", "Failed"),
        ],
        default="pending"
    )
    n_voters = models.IntegerField(default=0)
    n_noticias = models.IntegerField(default=0)
    n_clusters = models.IntegerField(default=0)
    computation_time = models.FloatField(
        null=True,
        blank=True,
        help_text="Computation time in seconds"
    )
    parameters = models.JSONField(
        default=dict,
        help_text="Clustering parameters (k, time_window, etc.)"
    )
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at', 'status']),
        ]

    def __str__(self):
        return (
            f"ClusterRun {self.id} - "
            f"{self.status} - {self.n_voters} voters"
        )


class VoterCluster(models.Model):
    """
    Store cluster results from a clustering run.
    Supports hierarchical clustering: base → group → subgroup.
    """
    run = models.ForeignKey(
        VoterClusterRun,
        on_delete=models.CASCADE,
        related_name='clusters'
    )
    cluster_id = models.IntegerField(
        help_text="Cluster identifier within this run"
    )
    cluster_type = models.CharField(
        max_length=20,
        choices=[
            ("base", "Base cluster"),
            ("group", "Group cluster"),
            ("subgroup", "Subgroup cluster"),
        ]
    )
    parent_cluster = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='subclusters',
        help_text="Parent cluster for hierarchical structure"
    )
    size = models.IntegerField(help_text="Number of voters in this cluster")
    centroid_x = models.FloatField(help_text="X coordinate of cluster center")
    centroid_y = models.FloatField(help_text="Y coordinate of cluster center")
    consensus_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Within-cluster agreement (0-1)"
    )
    metadata = models.JSONField(
        default=dict,
        help_text="Additional cluster metadata (radius, variance, etc.)"
    )

    # LLM-generated description fields (only for group clusters)
    llm_name = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="LLM-generated cluster name"
    )
    llm_description = models.TextField(
        null=True,
        blank=True,
        help_text="LLM-generated cluster description"
    )
    top_entities_positive = models.JSONField(
        default=list,
        help_text="Top entities viewed positively by this cluster"
    )
    top_entities_negative = models.JSONField(
        default=list,
        help_text="Top entities viewed negatively by this cluster"
    )
    description_generated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the LLM description was generated"
    )

    class Meta:
        unique_together = [['run', 'cluster_type', 'cluster_id']]
        indexes = [
            models.Index(fields=['run', 'cluster_type']),
            models.Index(fields=['run', 'consensus_score']),
        ]

    def __str__(self):
        return (
            f"{self.cluster_type.capitalize()} Cluster "
            f"{self.cluster_id} (size={self.size})"
        )


class VoterProjection(models.Model):
    """
    Store 2D PCA projections for each voter in a clustering run.
    Allows visualization of voter positions in 2D space.
    """
    run = models.ForeignKey(
        VoterClusterRun,
        on_delete=models.CASCADE,
        related_name='projections'
    )
    voter_type = models.CharField(
        max_length=10,
        choices=[
            ("session", "Session-based voter"),
            ("user", "Authenticated user"),
        ]
    )
    voter_id = models.CharField(
        max_length=255,
        help_text="Session key or user ID"
    )
    projection_x = models.FloatField(help_text="X coordinate in PCA space")
    projection_y = models.FloatField(help_text="Y coordinate in PCA space")
    n_votes_cast = models.IntegerField(
        help_text="Number of votes cast by this voter"
    )

    class Meta:
        unique_together = [['run', 'voter_type', 'voter_id']]
        indexes = [
            models.Index(fields=['voter_type', 'voter_id']),
            models.Index(fields=['run', 'voter_type']),
        ]

    def __str__(self):
        return (
            f"{self.voter_type}:{self.voter_id} "
            f"at ({self.projection_x:.2f}, {self.projection_y:.2f})"
        )


class NoticiaProjection(models.Model):
    """
    Store 2D PCA projections for each noticia in a clustering run.
    Part of the biplot visualization: noticias and voters in the same space.

    Noticias are projected using SVD dual projection:
    - Voters: U @ S (rows of vote matrix)
    - Noticias: Vt.T @ S (columns of vote matrix)

    This places noticias near the voters who voted positively on them.
    """
    run = models.ForeignKey(
        VoterClusterRun,
        on_delete=models.CASCADE,
        related_name='noticia_projections'
    )
    noticia = models.ForeignKey(
        Noticia,
        on_delete=models.CASCADE,
        related_name='cluster_projections'
    )
    projection_x = models.FloatField(help_text="X coordinate in PCA space")
    projection_y = models.FloatField(help_text="Y coordinate in PCA space")
    n_votes = models.IntegerField(
        help_text="Total votes received by this noticia"
    )

    class Meta:
        unique_together = [['run', 'noticia']]
        indexes = [
            models.Index(fields=['run']),
        ]

    def __str__(self):
        return (
            f"Noticia {self.noticia_id} "
            f"at ({self.projection_x:.2f}, {self.projection_y:.2f})"
        )


class VoterClusterMembership(models.Model):
    """
    Junction table linking voters to their assigned clusters.
    A voter can be in one cluster per cluster_type per run.
    """
    cluster = models.ForeignKey(
        VoterCluster,
        on_delete=models.CASCADE,
        related_name='members'
    )
    voter_type = models.CharField(max_length=10)
    voter_id = models.CharField(max_length=255)
    distance_to_centroid = models.FloatField(
        null=True,
        blank=True,
        help_text="Euclidean distance to cluster centroid"
    )

    class Meta:
        unique_together = [['cluster', 'voter_type', 'voter_id']]
        indexes = [
            models.Index(fields=['voter_type', 'voter_id']),
            models.Index(fields=['cluster']),
        ]

    def __str__(self):
        return f"{self.voter_type}:{self.voter_id} in cluster {self.cluster.cluster_id}"


class ClusterVotingPattern(models.Model):
    """
    Aggregated voting patterns for a cluster on a specific noticia.
    Shows how a cluster collectively voted on each news article.
    """
    cluster = models.ForeignKey(
        VoterCluster,
        on_delete=models.CASCADE,
        related_name='voting_patterns'
    )
    noticia = models.ForeignKey(Noticia, on_delete=models.CASCADE)
    count_buena = models.IntegerField(default=0)
    count_mala = models.IntegerField(default=0)
    count_neutral = models.IntegerField(default=0)
    consensus_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Degree of agreement on this noticia (0-1)"
    )
    majority_opinion = models.CharField(
        max_length=10,
        blank=True,
        help_text="buena/mala/neutral"
    )

    class Meta:
        unique_together = [['cluster', 'noticia']]
        indexes = [
            models.Index(fields=['cluster', 'consensus_score']),
            models.Index(fields=['cluster', 'majority_opinion']),
        ]

    def __str__(self):
        return (
            f"Cluster {self.cluster.cluster_id} on {self.noticia.mostrar_titulo[:30]}: "
            f"{self.majority_opinion or 'no consensus'}"
        )


class ReengagementEmailLog(models.Model):
    """
    Track when re-engagement emails are sent to users.
    Prevents sending too many emails in a short period.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reengagement_emails'
    )
    sent_at = models.DateTimeField(auto_now_add=True)
    email_type = models.CharField(
        max_length=50,
        default="reengagement",
        help_text="Type of re-engagement email sent"
    )
    
    class Meta:
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['user', '-sent_at']),
        ]
    
    def __str__(self):
        return f"Email to {self.user.email} at {self.sent_at}"


class UserProfile(models.Model):
    """
    Extended user profile for additional settings.
    Created automatically when a user signs up.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    alias = models.CharField(
        max_length=30,
        blank=True,
        help_text="Public alias shown on cluster map"
    )
    show_alias_on_map = models.BooleanField(
        default=False,
        help_text="Display alias on cluster visualization"
    )
    weekly_email_enabled = models.BooleanField(
        default=False,
        help_text="Receive weekly emails with news in your area of interest"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user']),
        ]
    
    def __str__(self):
        return f"Profile for {self.user.email}"
    
    @property
    def display_name(self):
        """Get display name: alias if set and visible, otherwise anonymous."""
        if self.alias and self.show_alias_on_map:
            return self.alias
        return "Anónimo"
