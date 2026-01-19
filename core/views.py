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
from django.utils.decorators import method_decorator
from django.core.exceptions import ValidationError
from django_ratelimit.decorators import ratelimit
from core.models import (
    Noticia,
    Voto,
    Entidad,
    VoterClusterRun,
    VoterClusterMembership,
)
import validators
from urllib.parse import urlparse


from core.forms import NoticiaForm
from django.urls import reverse_lazy
from django.db.models import Count, Q, F
import logging

logger = logging.getLogger(__name__)

# Blacklist de dominios conocidos por spam/malware
BLACKLISTED_DOMAINS = [
    'spam.com',
    'malware.net',
    'example-spam.org',
]

# TLDs sospechosos
SUSPICIOUS_TLDS = [
    '.ru', '.cn', '.tk', '.ml', '.ga', '.cf', '.gq',
]


def validate_noticia_url(url):
    """
    Valida que la URL sea legítima y segura.
    
    Raises:
        ValidationError: Si la URL no es válida
    
    Returns:
        bool: True si la URL es válida
    """
    if not validators.url(url):
        raise ValidationError("URL inválida")
    
    if not url.startswith('https://'):
        raise ValidationError("Solo se permiten URLs HTTPS")
    
    try:
        domain = urlparse(url).netloc.lower()
    except Exception:
        raise ValidationError("Dominio inválido")
    
    if any(blacklisted in domain for blacklisted in BLACKLISTED_DOMAINS):
        raise ValidationError("Este dominio no está permitido")
    
    if any(url.lower().endswith(tld) for tld in SUSPICIOUS_TLDS):
        logger.warning(f"Suspicious TLD in URL: {url}")
    
    if len(url) > 2000:
        raise ValidationError("URL demasiado larga")
    
    return True


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

    def paginate_queryset(self, queryset, page_size):
        """
        Override to handle out-of-range pages gracefully.
        When filtering 'nuevas' (unvoted news), items disappear as users vote,
        which can make previously valid pages no longer exist.
        Instead of 404, return empty list with has_next=False.
        """
        from django.core.paginator import Paginator, EmptyPage

        paginator = Paginator(queryset, page_size)
        page_kwarg = self.page_kwarg
        page = self.kwargs.get(page_kwarg) or self.request.GET.get(page_kwarg) or 1

        try:
            page_number = int(page)
        except ValueError:
            page_number = 1

        try:
            page_obj = paginator.page(page_number)
            return (paginator, page_obj, page_obj.object_list, page_obj.has_other_pages())
        except EmptyPage:
            # Page out of range - return empty page with has_next=False
            # This happens when user votes on all items and next page
            # no longer exists
            page_obj = paginator.page(paginator.num_pages) if paginator.num_pages > 0 else None
            if page_obj:
                # Return last valid page's info but with empty object list
                # to signal no more content
                class EmptyPageObj:
                    def __init__(self):
                        self.object_list = []
                        self.has_next_val = False
                        self.has_previous_val = paginator.num_pages > 0
                        self.number = page_number

                    def has_next(self):
                        return self.has_next_val

                    def has_previous(self):
                        return self.has_previous_val

                    def next_page_number(self):
                        return self.number + 1

                    def previous_page_number(self):
                        return self.number - 1

                empty_page = EmptyPageObj()
                return (paginator, empty_page, [], False)
            else:
                # No pages at all
                class EmptyPageObj:
                    def __init__(self):
                        self.object_list = []
                        self.has_next_val = False
                        self.has_previous_val = False
                        self.number = 1

                    def has_next(self):
                        return False

                    def has_previous(self):
                        return False

                empty_page = EmptyPageObj()
                return (paginator, empty_page, [], False)

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
            return "noticias nuevas"

        # Show all news
        if filter_param == "todas":
            return "todas las noticias"

        # User opinion filters (authenticated or session-based)
        if filter_param == "buena_mi":
            return "buenas noticias según mi opinión"
        elif filter_param == "mala_mi":
            return "malas noticias según mi opinión"

        # Majority opinion filters
        elif filter_param == "buena_mayoria":
            return "buenas noticias según la mayoría"
        elif filter_param == "mala_mayoria":
            return "malas noticias según la mayoría"

        # Bubble filters
        elif filter_param == "cluster_consenso_buena":
            return "buenas noticias según mi burbuja"
        elif filter_param == "otras_burbujas":
            return "noticias desde otras burbujas"

        # Entity filters
        elif filter_param.startswith("mencionan_") and entidad_id:
            try:
                entidad = Entidad.objects.get(id=entidad_id)

                if filter_param == "mencionan_a":
                    return f"todas las menciones de {entidad.nombre}"
                elif filter_param == "mencionan_positiva":
                    return f"menciones positivas de {entidad.nombre}"
                elif filter_param == "mencionan_negativa":
                    return f"menciones negativas de {entidad.nombre}"
            except (Entidad.DoesNotExist, ValueError):
                return "noticias filtradas por entidad"

        # Default for unknown filters
        return "noticias filtradas"

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
        
        # Check if should show signup prompt (for empty state)
        if not self.request.user.is_authenticated:
            total_votes = Voto.objects.filter(**lookup_data).count()
            context["should_show_signup_prompt"] = total_votes >= 3
            context["total_votes_count"] = total_votes
        else:
            context["should_show_signup_prompt"] = False

        # Get entities available in the current filtered queryset
        queryset = self.get_queryset()
        available_entity_ids = queryset.values_list(
            'entidades__entidad_id', flat=True
        ).distinct()
        context["entidades"] = Entidad.objects.filter(
            id__in=available_entity_ids
        ).order_by('nombre')

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
            # Try to find voter's cluster membership - prefer group clusters
            try:
                # First try to get group cluster membership
                membership = VoterClusterMembership.objects.filter(
                    cluster__run=cluster_run,
                    cluster__cluster_type='group',
                    voter_type=voter_type,
                    voter_id=voter_id
                ).select_related('cluster').first()

                # Fallback to base cluster if no group cluster
                if not membership:
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
                        'llm_name': my_cluster_obj.llm_name,
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
            from django.template.loader import render_to_string

            self.template_name = "noticias/timeline_items.html"

            # When loading just the items via HTMX, also update entity filter
            if self.request.headers.get("HX-Target") == "timeline-items":
                # Get the main response
                response = super().render_to_response(
                    context, **response_kwargs
                )

                # Render the response to make content accessible
                response.render()

                # Render entity filter partial with OOB swap attribute
                entity_filter_html = render_to_string(
                    "noticias/entity_filter.html",
                    {"entidades": context.get("entidades", [])},
                    request=self.request
                )

                # Add hx-swap-oob to the entity filter section
                entity_filter_with_oob = entity_filter_html.replace(
                    '<div id="entity-filter-section">',
                    '<div id="entity-filter-section" hx-swap-oob="true">'
                )

                # Append out-of-band swap for entity filter
                response.content = (
                    response.content + entity_filter_with_oob.encode()
                )

                # Send filter description update via HX-Trigger
                import json
                response["HX-Trigger"] = json.dumps({
                    "updateActiveFilters": {
                        "description": context["filter_description"]
                    }
                })
                return response

        return super().render_to_response(context, **response_kwargs)


@method_decorator(ratelimit(key='ip', rate='100/h', method='POST'), name='dispatch')
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
            logger.info("[Vote Debug] Returning empty response (item will be removed)")
            
            # Check if should show signup prompt on 3rd vote
            if not request.user.is_authenticated:
                total_votes = Voto.objects.filter(**lookup_data).count()
                logger.info(f"[Signup Prompt Debug] Anonymous user - Total votes: {total_votes}")
                if total_votes == 3:
                    logger.info("[Signup Prompt Debug] ✓ Showing signup prompt (3rd vote)")
                    # Show signup prompt via out-of-band swap
                    from django.template.loader import render_to_string
                    signup_prompt_html = render_to_string(
                        "noticias/signup_prompt.html",
                        {"show_signup_prompt": True, "total_votes": total_votes},
                        request=request
                    )
                    return HttpResponse(signup_prompt_html)
                else:
                    logger.info(f"[Signup Prompt Debug] Not 3rd vote yet (need 3, have {total_votes})")
            else:
                logger.info("[Signup Prompt Debug] User is authenticated, no prompt needed")
            
            return HttpResponse("")

        # Check if voting from detail page
        from_detail_page = (
            request.headers.get("HX-Target") == "vote-form-detail"
            or "vote-form-detail" in request.POST.get("hx-target", "")
        )

        if from_detail_page:
            # Count total votes for this voter (for signup prompt)
            total_votes = Voto.objects.filter(**lookup_data).count()
            
            # Show signup prompt on 3rd vote for anonymous users
            show_signup_prompt = (
                not request.user.is_authenticated and 
                total_votes == 3
            )
            
            if not request.user.is_authenticated:
                logger.info(f"[Signup Prompt Debug] Detail page - Total votes: {total_votes}, Show prompt: {show_signup_prompt}")
            
            # Return post-vote message with CTA to more news
            context = {
                "noticia": noticia,
                "vote": vote,
                "show_signup_prompt": show_signup_prompt,
                "total_votes": total_votes,
            }
            return render(request, "noticias/vote_confirmed.html", context)

        # Render the updated vote area partial (for timeline)
        # Count total votes for signup prompt
        total_votes = Voto.objects.filter(**lookup_data).count()
        show_signup_prompt = (
            not request.user.is_authenticated and 
            total_votes == 3
        )
        
        context = {
            "noticia": noticia,
            "user": request.user,
            "voter_session": (
                lookup_data.get("session_key")
                if not request.user.is_authenticated
                else None
            ),
        }
        
        # Render vote area
        vote_area_html = render(request, "noticias/vote_area.html", context).content.decode()
        
        # If it's the 3rd vote, append signup prompt with out-of-band swap
        if show_signup_prompt:
            from django.template.loader import render_to_string
            signup_prompt_html = render_to_string(
                "noticias/signup_prompt.html",
                {"show_signup_prompt": True, "total_votes": total_votes},
                request=request
            )
            return HttpResponse(vote_area_html + signup_prompt_html)
        
        return HttpResponse(vote_area_html)


@method_decorator(ratelimit(key='ip', rate='10/h', method='POST'), name='dispatch')
class NoticiaCreateView(FormView):  # NO LoginRequiredMixin - allow anonymous
    template_name = "noticias/timeline_fragment.html"
    form_class = NoticiaForm
    success_url = reverse_lazy("timeline")

    def form_valid(self, form):
        vote_opinion = form.cleaned_data.get("opinion")
        enlace = form.cleaned_data.get("enlace")

        # Validate URL
        try:
            validate_noticia_url(enlace)
        except ValidationError as e:
            logger.warning(f"[NoticiaCreate] Invalid URL rejected: {enlace} - {str(e)}")
            form.add_error('enlace', str(e))
            return self.form_invalid(form)

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

                    # First try to get group cluster membership
                    membership = VoterClusterMembership.objects.filter(
                        cluster__run=cluster_run,
                        cluster__cluster_type='group',
                        voter_type=voter_type,
                        voter_id=voter_id
                    ).select_related('cluster').first()

                    # Fallback to base cluster if no group cluster
                    if not membership:
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
                            'llm_name': my_cluster_obj.llm_name,
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
