# views.py

from django.views.generic import (
    ListView,
    View,
    FormView,
    TemplateView,
    DetailView,
)
from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponseBadRequest, HttpResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from core.models import (
    Noticia,
    Voto,
    Entidad,
    VoterClusterRun,
    VoterClusterMembership,
)


from core.forms import NoticiaForm
from django.urls import reverse_lazy
from django.db.models import Count, Q, F
import logging

logger = logging.getLogger(__name__)


def get_voter_identifier(request):
    """
    Get identifier for current voter (user or session).
    Returns dict with either 'usuario' or 'session_key' key.
    Prioritizes extension session if available for consistency.
    """
    logger.info("=" * 60)
    logger.info("[Session Debug] get_voter_identifier called")
    logger.info(f"[Session Debug] Path: {request.path}")
    logger.info(f"[Session Debug] Method: {request.method}")

    if request.user.is_authenticated:
        logger.info(f"[Session Debug] ✓ Authenticated user: {request.user.username}")
        return {"usuario": request.user}, {"usuario": request.user}
    else:
        # Check for extension session first (for consistency)
        # Try header first (for HTMX requests), then cookie (for initial page load)
        extension_session = request.headers.get("X-Extension-Session")

        if not extension_session:
            extension_session = request.COOKIES.get("memoria_extension_session")
            logger.info(
                f"[Session Debug] Extension session from cookie: {extension_session}"
            )
        else:
            logger.info(
                f"[Session Debug] Extension session from header: {extension_session}"
            )

        if extension_session:
            logger.info(
                f"[Session Debug] ✓ Using extension session: {extension_session}"
            )
            return (
                {"session_key": extension_session},
                {"session_key": extension_session},
            )

        # Fall back to Django session for web users
        django_session = request.session.session_key
        logger.info(f"[Session Debug] Django session key: {django_session}")

        if not django_session:
            request.session.create()
            django_session = request.session.session_key
            logger.info(
                f"[Session Debug] ✓ Created new Django session: {django_session}"
            )
        else:
            logger.info(
                f"[Session Debug] ✓ Using existing Django session: {django_session}"
            )

        return {"session_key": django_session}, {"session_key": django_session}


class NewsTimelineView(ListView):
    model = Noticia
    template_name = "noticias/timeline.html"
    context_object_name = "noticias"
    ordering = ["-fecha_agregado"]
    paginate_by = 10

    def get(self, request, *args, **kwargs):
        # Get voter identifier (user or session)
        voter_data, lookup_data = get_voter_identifier(request)

        logger.info(f"[Timeline Debug] Voter data: {voter_data}")
        logger.info(f"[Timeline Debug] Lookup data: {lookup_data}")

        return super().get(request, *args, **kwargs)

    def get_filter_description(self):
        """
        Maps the applied filters to natural language descriptions.
        Returns a string describing the current filter in natural language.
        """
        filter_param = self.request.GET.get("filter")
        entidad_id = self.request.GET.get("entidad")

        # Default: show new news (unvoted)
        if not filter_param or filter_param == "nuevas":
            return "Estás viendo las noticias que aún no votaste"

        # Show all news
        if filter_param == "todas":
            return "Estás viendo todas las noticias"

        # User opinion filters (authenticated or session-based)
        if filter_param == "buena_mi":
            return "Estás viendo solo las noticias que marcaste como buenas"
        elif filter_param == "mala_mi":
            return "Estás viendo solo las noticias que marcaste como malas"

        # Majority opinion filters
        elif filter_param == "buena_mayoria":
            return "Estás viendo las noticias que la mayoría considera buenas"
        elif filter_param == "mala_mayoria":
            return "Estás viendo las noticias que la mayoría considera malas"

        # Bubble filters
        elif filter_param == "cluster_consenso_buena":
            return "Estás viendo noticias con alto consenso (buenas) en tu burbuja"
        elif filter_param == "otras_burbujas":
            return "Estás viendo noticias desde perspectivas diferentes a tu burbuja"

        # Entity filters
        elif filter_param.startswith("mencionan_") and entidad_id:
            try:
                entidad = Entidad.objects.get(id=entidad_id)

                if filter_param == "mencionan_a":
                    return f"Estás viendo las noticias que mencionan a {entidad.nombre}"
                elif filter_param == "mencionan_positiva":
                    return f"Estás viendo las noticias que mencionan positivamente a {entidad.nombre}"
                elif filter_param == "mencionan_negativa":
                    return f"Estás viendo las noticias que mencionan negativamente a {entidad.nombre}"
            except (Entidad.DoesNotExist, ValueError):
                return "Estás viendo noticias filtradas por entidad"

        # Default for unknown filters
        return "Estás viendo noticias filtradas"

    def get_queryset(self):
        queryset = super().get_queryset()

        # Get voter identifier (handles extension session priority)
        voter_data, lookup_data = get_voter_identifier(self.request)

        # Get parameters from different possible sources
        filter_param = self.request.GET.get("filter", "")
        entidad_id = self.request.GET.get("entidad", "")
        logger.info(f"[Timeline Debug] Filter: {filter_param}")

        # Try to get from POST if not in GET
        if not filter_param and "filter" in self.request.POST:
            filter_param = self.request.POST.get("filter")
        if not entidad_id and "entidad" in self.request.POST:
            entidad_id = self.request.POST.get("entidad")

        # Check if entity is in the path parameters
        if (
            not entidad_id
            and hasattr(self.request, "resolver_match")
            and self.request.resolver_match
        ):
            entidad_id = self.request.resolver_match.kwargs.get("entidad", "")

        # Default filter: show news user hasn't voted on (nuevas)

        if not filter_param or filter_param == "nuevas":
            logger.info(f"[Timeline Debug] Filtering with: {lookup_data}")
            if self.request.user.is_authenticated:
                queryset = queryset.exclude(votos__usuario=self.request.user)
            elif lookup_data.get("session_key"):
                queryset = queryset.exclude(
                    votos__session_key=lookup_data["session_key"]
                )
        # Show all news
        elif filter_param == "todas":
            pass  # No filtering needed
        # Filter by user's votes (authenticated or anonymous)
        elif filter_param == "buena_mi":
            if self.request.user.is_authenticated:
                queryset = queryset.filter(
                    votos__usuario=self.request.user, votos__opinion="buena"
                )
            elif lookup_data.get("session_key"):
                queryset = queryset.filter(
                    votos__session_key=lookup_data["session_key"],
                    votos__opinion="buena",
                )
        elif filter_param == "mala_mi":
            if self.request.user.is_authenticated:
                queryset = queryset.filter(
                    votos__usuario=self.request.user, votos__opinion="mala"
                )
            elif lookup_data.get("session_key"):
                queryset = queryset.filter(
                    votos__session_key=lookup_data["session_key"],
                    votos__opinion="mala",
                )
        elif filter_param == "buena_mayoria":
            # Filter by news with a majority of good votes
            queryset = queryset.annotate(
                good_count=Count("votos", filter=Q(votos__opinion="buena")),
                total_count=Count("votos"),
            ).filter(good_count__gt=F("total_count") / 2)
        elif filter_param == "mala_mayoria":
            # Filter by news with a majority of bad votes
            queryset = queryset.annotate(
                bad_count=Count("votos", filter=Q(votos__opinion="mala")),
                total_count=Count("votos"),
            ).filter(bad_count__gt=F("total_count") / 2)
        # Entity filters
        elif filter_param == "mencionan_a" and entidad_id:
            queryset = queryset.filter(entidades__entidad__pk=entidad_id)
        elif filter_param == "mencionan_positiva" and entidad_id:
            queryset = queryset.filter(
                entidades__entidad__pk=entidad_id, entidades__sentimiento="positivo"
            )
        elif filter_param == "mencionan_negativa" and entidad_id:
            queryset = queryset.filter(
                entidades__entidad__pk=entidad_id, entidades__sentimiento="negativo"
            )
        # Cluster filters
        elif filter_param == "cluster_consenso_buena":
            # Show news with high consensus as "buena" in voter's cluster
            from core.models import (
                VoterClusterRun,
                VoterClusterMembership,
                ClusterVotingPattern,
            )

            cluster_run = VoterClusterRun.objects.filter(
                status='completed'
            ).order_by('-created_at').first()

            if cluster_run:
                voter_type = (
                    'user' if self.request.user.is_authenticated else 'session'
                )
                voter_id = (
                    str(self.request.user.id)
                    if self.request.user.is_authenticated
                    else lookup_data.get("session_key")
                )

                membership = VoterClusterMembership.objects.filter(
                    cluster__run=cluster_run,
                    cluster__cluster_type='base',
                    voter_type=voter_type,
                    voter_id=voter_id
                ).select_related('cluster').first()

                if membership:
                    # Get noticias with high consensus in this cluster
                    high_consensus_patterns = ClusterVotingPattern.objects.filter(
                        cluster=membership.cluster,
                        majority_opinion='buena',
                        consensus_score__gte=0.7
                    ).values_list('noticia_id', flat=True)

                    queryset = queryset.filter(
                        id__in=high_consensus_patterns
                    )
                else:
                    # No cluster membership, return empty
                    queryset = queryset.none()
            else:
                # No clustering data, return empty
                queryset = queryset.none()
        # Other bubbles filter
        elif filter_param == "otras_burbujas":
            from core.models import (
                VoterClusterRun,
                VoterClusterMembership,
                ClusterVotingPattern,
                Voto,
            )

            cluster_run = VoterClusterRun.objects.filter(
                status='completed'
            ).order_by('-created_at').first()

            if cluster_run:
                voter_type = (
                    'user' if self.request.user.is_authenticated else 'session'
                )
                voter_id = (
                    str(self.request.user.id)
                    if self.request.user.is_authenticated
                    else lookup_data.get("session_key")
                )

                membership = VoterClusterMembership.objects.filter(
                    cluster__run=cluster_run,
                    cluster__cluster_type='base',
                    voter_type=voter_type,
                    voter_id=voter_id
                ).select_related('cluster').first()

                if membership:
                    # Get noticias where this voter's opinion differs
                    # from their bubble's majority
                    my_cluster = membership.cluster

                    # Get all votes by this voter
                    my_votes = Voto.objects.filter(**lookup_data)
                    my_votes_dict = {
                        v.noticia_id: v.opinion for v in my_votes
                    }

                    # Get cluster patterns
                    cluster_patterns = ClusterVotingPattern.objects.filter(
                        cluster=my_cluster,
                        noticia_id__in=my_votes_dict.keys()
                    )

                    # Find noticias where voter disagrees with bubble
                    different_noticias = []
                    for pattern in cluster_patterns:
                        my_opinion = my_votes_dict.get(pattern.noticia_id)
                        if (my_opinion and
                            pattern.majority_opinion and
                            my_opinion != pattern.majority_opinion):
                            different_noticias.append(pattern.noticia_id)

                    if different_noticias:
                        queryset = queryset.filter(id__in=different_noticias)
                    else:
                        # No disagreements found, show unvoted news
                        queryset = queryset.exclude(
                            votos__in=Voto.objects.filter(**lookup_data)
                        )
                else:
                    # No cluster membership
                    queryset = queryset.none()
            else:
                # No clustering data
                queryset = queryset.none()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get voter identifier (handles extension session priority)
        voter_data, lookup_data = get_voter_identifier(self.request)

        # Only include the form in the initial full-page load
        if not self.request.headers.get("HX-Request"):
            context["form"] = NoticiaForm()

        # Add current filter to context
        current_filter = self.request.GET.get("filter", "nuevas")
        context["current_filter"] = current_filter

        # Add filter description to context
        context["filter_description"] = self.get_filter_description()
        context["entidades"] = Entidad.objects.all()

        # Add voter identifier to context (for templates to check votes)
        if self.request.user.is_authenticated:
            context["voter_user"] = self.request.user
            context["voter_session"] = None
            voter_type = 'user'
            voter_id = str(self.request.user.id)
        else:
            context["voter_user"] = None
            context["voter_session"] = lookup_data.get("session_key")
            voter_type = 'session'
            voter_id = lookup_data.get("session_key")

        # Add user votes to noticias
        if 'noticias' in context:
            noticia_ids = [n.id for n in context['noticias']]
            user_votes = Voto.objects.filter(
                noticia_id__in=noticia_ids,
                **lookup_data
            ).values('noticia_id', 'opinion')
            votes_dict = {v['noticia_id']: v['opinion'] for v in user_votes}

            for noticia in context['noticias']:
                noticia.user_vote = votes_dict.get(noticia.id)

        # Add cluster information if available
        cluster_run = VoterClusterRun.objects.filter(
            status='completed'
        ).order_by('-created_at').first()

        if cluster_run and voter_id:
            # Try to find voter's cluster membership
            try:
                membership = VoterClusterMembership.objects.filter(
                    cluster__run=cluster_run,
                    cluster__cluster_type='base',
                    voter_type=voter_type,
                    voter_id=voter_id
                ).select_related('cluster').first()

                if membership:
                    my_cluster_obj = membership.cluster
                    context["my_cluster"] = {
                        'id': my_cluster_obj.cluster_id,
                        'size': my_cluster_obj.size,
                        'consensus': my_cluster_obj.consensus_score,
                        'centroid_x': my_cluster_obj.centroid_x,
                        'centroid_y': my_cluster_obj.centroid_y,
                    }
                    context["has_cluster"] = True

                    # Fetch cluster voting patterns for noticias
                    # in timeline
                    from core.models import ClusterVotingPattern
                    noticia_ids = [n.id for n in context['noticias']]
                    patterns = ClusterVotingPattern.objects.filter(
                        cluster=my_cluster_obj,
                        noticia_id__in=noticia_ids
                    ).select_related('noticia')

                    # Create lookup dict for templates
                    cluster_patterns = {
                        p.noticia_id: {
                            'majority_opinion': p.majority_opinion,
                            'consensus_score': p.consensus_score,
                            'count_buena': p.count_buena,
                            'count_mala': p.count_mala,
                            'count_neutral': p.count_neutral,
                            'total_votes': (
                                p.count_buena +
                                p.count_mala +
                                p.count_neutral
                            ),
                        }
                        for p in patterns
                    }
                    context["cluster_patterns"] = cluster_patterns
                else:
                    context["has_cluster"] = False
            except Exception as e:
                logger.error(f"Error fetching cluster membership: {e}")
                context["has_cluster"] = False
        else:
            context["has_cluster"] = False

        return context

    def render_to_response(self, context, **response_kwargs):
        # If the request is via HTMX, return just the list items partial
        if self.request.headers.get("HX-Request"):
            self.template_name = "noticias/timeline_items.html"

            # When loading just the items via HTMX, update the active filters section
            if self.request.headers.get("HX-Target") == "timeline-items":
                response_kwargs.setdefault("headers", {})
                response_kwargs["headers"]["HX-Trigger"] = (
                    '{"updateActiveFilters": {"description": "'
                    + context["filter_description"]
                    + '"}}'
                )
        return super().render_to_response(context, **response_kwargs)


class VoteView(View):  # NO LoginRequiredMixin - allow anonymous
    def post(self, request, pk):
        logger.info(f"[Vote Debug] Voting on noticia {pk}")

        noticia = get_object_or_404(Noticia, pk=pk)
        opinion = request.POST.get("opinion")

        logger.info(f"[Vote Debug] Opinion: {opinion}")

        if opinion not in ["buena", "mala", "neutral"]:
            return HttpResponseBadRequest("Invalid vote")

        # Get voter identifier (user or session)
        voter_data, lookup_data = get_voter_identifier(request)

        logger.info(f"[Vote Debug] Voter data: {voter_data}")
        logger.info(f"[Vote Debug] Lookup data: {lookup_data}")

        # Update or create vote
        vote, created = Voto.objects.update_or_create(
            noticia=noticia, **lookup_data, defaults={**voter_data, "opinion": opinion}
        )

        logger.info(
            f"[Vote Debug] Vote {'created' if created else 'updated'}: {vote.id}"
        )

        # Trigger clustering check asynchronously after vote
        if created or opinion != vote.opinion:
            from core.tasks import check_and_trigger_clustering
            check_and_trigger_clustering.apply_async(countdown=5)

        # If voting from the "nuevas" filter, return empty to remove item
        on_nuevas_filter = request.POST.get("on_nuevas_filter") == "true"
        logger.info(f"[Vote Debug] On nuevas filter: {on_nuevas_filter}")

        if on_nuevas_filter:
            logger.info(
                "[Vote Debug] Returning empty response "
                "(item will be removed)"
            )
            return HttpResponse("")

        # Check if voting from detail page
        from_detail_page = (
            request.headers.get("HX-Target") == "vote-form-detail"
            or "vote-form-detail" in request.POST.get("hx-target", "")
        )

        if from_detail_page:
            # Return post-vote message with CTA to more news
            context = {
                "noticia": noticia,
                "vote": vote,
            }
            return render(request, "noticias/vote_confirmed.html", context)

        # Render the updated vote area partial (for timeline)
        context = {
            "noticia": noticia,
            "user": request.user,
            "voter_session": (
                lookup_data.get("session_key")
                if not request.user.is_authenticated
                else None
            ),
        }
        return render(request, "noticias/vote_area.html", context)


class NoticiaCreateView(FormView):  # NO LoginRequiredMixin - allow anonymous
    template_name = "noticias/timeline_fragment.html"
    form_class = NoticiaForm
    success_url = reverse_lazy("timeline")

    def form_valid(self, form):
        vote_opinion = form.cleaned_data.get("opinion")
        enlace = form.cleaned_data.get("enlace")

        # Get or create noticia
        noticia, created = Noticia.objects.get_or_create(
            enlace=enlace,
            defaults={
                "agregado_por": self.request.user
                if self.request.user.is_authenticated
                else None
            },
        )

        # Try to capture full HTML for better parsing
        html_captured = False
        if created and not noticia.captured_html:
            from core import url_requests
            from core.tasks import enrich_from_captured_html

            try:
                response = url_requests.get(enlace, timeout=10)
                if response.status_code == 200:
                    noticia.captured_html = response.text
                    noticia.save()
                    html_captured = True
                    logger.info(
                        f"Captured HTML for noticia {noticia.id} from web"
                    )
                    # Trigger async enrichment with LLM
                    enrich_from_captured_html.delay(noticia.id)
                else:
                    logger.warning(
                        f"Failed to capture HTML for {enlace}: "
                        f"HTTP {response.status_code}"
                    )
            except Exception as e:
                logger.warning(
                    f"Could not capture HTML for {enlace}: {e}"
                )

        # Fallback: fetch basic metadata if HTML capture failed
        if not html_captured and (created or not noticia.meta_titulo):
            try:
                noticia.update_meta_from_url()
            except Exception as e:
                logger.warning(f"Could not fetch metadata for {enlace}: {e}")

        # Get voter identifier (user or session)
        voter_data, lookup_data = get_voter_identifier(self.request)

        # Create or update vote
        Voto.objects.update_or_create(
            noticia=noticia,
            **lookup_data,
            defaults={**voter_data, "opinion": vote_opinion},
        )

        # For HTMX requests, re-render the entire timeline fragment
        if self.request.headers.get("HX-Request"):
            noticias = Noticia.objects.all().order_by("-fecha_agregado")
            response = render(
                self.request,
                "noticias/timeline_fragment.html",
                {
                    "noticias": noticias,
                    "form": self.get_form_class()(),
                    "filter_description": "Estás viendo todas las noticias",
                    "voter_user": self.request.user
                    if self.request.user.is_authenticated
                    else None,
                    "voter_session": lookup_data.get("session_key")
                    if not self.request.user.is_authenticated
                    else None,
                },
            )
            # Add HTMX response headers
            response["HX-Trigger"] = (
                '{"noticiaCreated": {"message": "Noticia guardada exitosamente"}}'
            )
            return response

        return redirect(self.success_url)

    def form_invalid(self, form):
        # For HTMX requests, return the form with errors
        if self.request.headers.get("HX-Request"):
            errors = form.errors
            error_message = (
                next(iter(errors.values()))[0]
                if errors
                else "Ha ocurrido un error al procesar el formulario"
            )

            logger.error(f"Form validation error: {errors}")

            # Get voter identifier (handles extension session priority)
            voter_data, lookup_data = get_voter_identifier(self.request)

            response = render(
                self.request,
                self.template_name,
                {
                    "form": form,
                    "filter_description": "Estás viendo todas las noticias",
                    "noticias": Noticia.objects.all().order_by("-fecha_agregado"),
                    "voter_user": self.request.user
                    if self.request.user.is_authenticated
                    else None,
                    "voter_session": lookup_data.get("session_key")
                    if not self.request.user.is_authenticated
                    else None,
                },
            )

            response["HX-Trigger"] = (
                f'{{"noticiaError": {{"message": "{error_message}"}}}}'
            )
            return response

        return super().form_invalid(form)


# Admin-only views (keep login required)
class RefreshNoticiaView(LoginRequiredMixin, View):
    """Admin only - refresh metadata for a news article."""

    def post(self, request, pk):
        noticia = get_object_or_404(Noticia, pk=pk)
        try:
            noticia.update_meta_from_url()
        except Exception as e:
            logger.error(f"Error refreshing noticia {pk}: {e}")
        return render(request, "noticias/timeline_item.html", {"noticia": noticia})


class DeleteNoticiaView(LoginRequiredMixin, View):
    """Admin only - delete a news article."""

    def post(self, request, pk):
        noticia = get_object_or_404(Noticia, pk=pk)
        noticia.delete()

        # For HTMX requests, return empty HTML (item removed)
        if request.headers.get("HX-Request"):
            return HttpResponse("")

        return redirect(reverse_lazy("timeline"))


class AcercaDeView(TemplateView):
    """Static page explaining the project vision and motivation."""

    template_name = "acerca_de.html"


class PrivacidadView(TemplateView):
    """Privacy policy page."""

    template_name = "privacidad.html"


class BienvenidaView(TemplateView):
    """Welcome page for extension installation."""

    template_name = "bienvenida.html"


class NoticiaDetailView(DetailView):
    """Individual article detail page with SEO optimization."""

    model = Noticia
    template_name = "noticias/noticia_detail.html"
    context_object_name = "noticia"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        noticia = self.get_object()

        # Get voter identifier to check if user has voted
        voter_data, lookup_data = get_voter_identifier(self.request)

        # Check if current user has voted on this article
        user_vote = Voto.objects.filter(
            noticia=noticia, **lookup_data
        ).first()
        context["user_vote"] = user_vote

        # Get vote counts
        vote_stats = noticia.votos.aggregate(
            total=Count("id"),
            buenas=Count("id", filter=Q(opinion="buena")),
            malas=Count("id", filter=Q(opinion="mala")),
            neutrales=Count("id", filter=Q(opinion="neutral")),
        )
        context["vote_stats"] = vote_stats

        # Determine majority opinion
        if vote_stats["buenas"] > vote_stats["malas"]:
            context["majority_opinion"] = "buena"
        elif vote_stats["malas"] > vote_stats["buenas"]:
            context["majority_opinion"] = "mala"
        else:
            context["majority_opinion"] = "neutral"

        # Add cluster information if available
        voter_type = 'user' if self.request.user.is_authenticated else 'session'
        voter_id = (
            str(self.request.user.id)
            if self.request.user.is_authenticated
            else lookup_data.get("session_key")
        )

        if voter_id:
            cluster_run = VoterClusterRun.objects.filter(
                status='completed'
            ).order_by('-created_at').first()

            if cluster_run:
                try:
                    from core.models import (
                        VoterClusterMembership,
                        ClusterVotingPattern,
                    )

                    membership = VoterClusterMembership.objects.filter(
                        cluster__run=cluster_run,
                        cluster__cluster_type='base',
                        voter_type=voter_type,
                        voter_id=voter_id
                    ).select_related('cluster').first()

                    if membership:
                        my_cluster_obj = membership.cluster
                        context["my_cluster"] = {
                            'id': my_cluster_obj.cluster_id,
                            'size': my_cluster_obj.size,
                            'consensus': my_cluster_obj.consensus_score,
                        }
                        context["has_cluster"] = True

                        # Get cluster voting pattern for this noticia
                        pattern = ClusterVotingPattern.objects.filter(
                            cluster=my_cluster_obj,
                            noticia=noticia
                        ).first()

                        if pattern:
                            context["cluster_pattern"] = {
                                'majority_opinion': pattern.majority_opinion,
                                'consensus_score': pattern.consensus_score,
                                'count_buena': pattern.count_buena,
                                'count_mala': pattern.count_mala,
                                'count_neutral': pattern.count_neutral,
                                'total_votes': (
                                    pattern.count_buena +
                                    pattern.count_mala +
                                    pattern.count_neutral
                                ),
                            }
                    else:
                        context["has_cluster"] = False
                except Exception as e:
                    logger.error(f"Error fetching cluster data: {e}")
                    context["has_cluster"] = False
            else:
                context["has_cluster"] = False
        else:
            context["has_cluster"] = False

        return context
