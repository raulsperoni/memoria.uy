# views.py

from django.views.generic import ListView, View, FormView
from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponseBadRequest
from django.contrib.auth.mixins import LoginRequiredMixin
from core.models import Noticia, Voto, Entidad
from core.forms import NoticiaForm
from django.urls import reverse_lazy
from django.db.models import Count, Q, F
import logging

logger = logging.getLogger(__name__)


def get_voter_identifier(request):
    """
    Get identifier for current voter (user or session).
    Returns dict with either 'usuario' or 'session_key' key.
    """
    if request.user.is_authenticated:
        return {'usuario': request.user}, {'usuario': request.user}
    else:
        # Anonymous user - use session
        if not request.session.session_key:
            request.session.create()  # Force session creation
        session_key = request.session.session_key
        return {'session_key': session_key}, {'session_key': session_key}


class NewsTimelineView(ListView):
    model = Noticia
    template_name = "noticias/timeline.html"
    context_object_name = "noticias"
    ordering = ["-fecha_agregado"]
    paginate_by = 10

    def get_filter_description(self):
        """
        Maps the applied filters to natural language descriptions.
        Returns a string describing the current filter in natural language.
        """
        filter_param = self.request.GET.get("filter")
        entidad_id = self.request.GET.get("entidad")

        # Default description when no filters are applied
        if not filter_param or filter_param == "todas":
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

        # Get parameters from different possible sources
        filter_param = self.request.GET.get("filter", "")
        entidad_id = self.request.GET.get("entidad", "")

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

        # Filter by user's votes (authenticated or anonymous)
        if filter_param == "buena_mi":
            if self.request.user.is_authenticated:
                queryset = queryset.filter(
                    votos__usuario=self.request.user, votos__opinion="buena"
                )
            elif self.request.session.session_key:
                queryset = queryset.filter(
                    votos__session_key=self.request.session.session_key,
                    votos__opinion="buena"
                )
        elif filter_param == "mala_mi":
            if self.request.user.is_authenticated:
                queryset = queryset.filter(
                    votos__usuario=self.request.user, votos__opinion="mala"
                )
            elif self.request.session.session_key:
                queryset = queryset.filter(
                    votos__session_key=self.request.session.session_key,
                    votos__opinion="mala"
                )
        elif filter_param == "buena_mayoria":
            # Filter by news with a majority of good votes
            queryset = queryset.annotate(
                good_count=Count("votos", filter=Q(votos__opinion="buena")),
                total_count=Count("votos")
            ).filter(good_count__gt=F("total_count") / 2)
        elif filter_param == "mala_mayoria":
            # Filter by news with a majority of bad votes
            queryset = queryset.annotate(
                bad_count=Count("votos", filter=Q(votos__opinion="mala")),
                total_count=Count("votos")
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
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Only include the form in the initial full-page load
        if not self.request.headers.get("HX-Request"):
            context["form"] = NoticiaForm()

        # Add filter description to context
        context["filter_description"] = self.get_filter_description()
        context["entidades"] = Entidad.objects.all()

        # Add voter identifier to context (for templates to check votes)
        if self.request.user.is_authenticated:
            context["voter_user"] = self.request.user
            context["voter_session"] = None
        else:
            context["voter_user"] = None
            context["voter_session"] = self.request.session.session_key

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
        noticia = get_object_or_404(Noticia, pk=pk)
        opinion = request.POST.get("opinion")

        if opinion not in ["buena", "mala", "neutral"]:
            return HttpResponseBadRequest("Invalid vote")

        # Get voter identifier (user or session)
        voter_data, lookup_data = get_voter_identifier(request)

        # Update or create vote
        Voto.objects.update_or_create(
            noticia=noticia,
            **lookup_data,
            defaults={**voter_data, "opinion": opinion}
        )

        # Render the updated vote area partial
        context = {
            "noticia": noticia,
            "user": request.user,
            "voter_session": request.session.session_key if not request.user.is_authenticated else None
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
                'agregado_por': self.request.user if self.request.user.is_authenticated else None
            }
        )

        # Fetch metadata (fast, synchronous)
        if created or not noticia.meta_titulo:
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
            defaults={**voter_data, "opinion": vote_opinion}
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
                    "voter_user": self.request.user if self.request.user.is_authenticated else None,
                    "voter_session": self.request.session.session_key if not self.request.user.is_authenticated else None,
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
            error_message = next(iter(errors.values()))[0] if errors else "Ha ocurrido un error al procesar el formulario"

            logger.error(f"Form validation error: {errors}")

            response = render(
                self.request,
                self.template_name,
                {
                    "form": form,
                    "filter_description": "Estás viendo todas las noticias",
                    "noticias": Noticia.objects.all().order_by("-fecha_agregado"),
                    "voter_user": self.request.user if self.request.user.is_authenticated else None,
                    "voter_session": self.request.session.session_key if not self.request.user.is_authenticated else None,
                },
            )

            response["HX-Trigger"] = f'{{"noticiaError": {{"message": "{error_message}"}}}}'
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
        return redirect(reverse_lazy("timeline"))
