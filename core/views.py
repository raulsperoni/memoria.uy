# views.py

from django.views.generic import ListView, View, FormView
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponseBadRequest
from django.contrib.auth.mixins import LoginRequiredMixin
from core.models import Noticia, Voto, Entidad
from core.forms import NoticiaForm
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.db.models import Count, Q, F
import time
import logging

logger = logging.getLogger(__name__)


class NewsTimelineView(ListView):
    model = Noticia
    template_name = "noticias/timeline.html"
    context_object_name = "noticias"
    ordering = ["-fecha_agregado"]
    paginate_by = 10  # Adjust the number as needed

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

        # User opinion filters
        if filter_param == "buena_mi" and self.request.user.is_authenticated:
            return "Estás viendo solo las noticias que marcaste como buenas"
        elif filter_param == "mala_mi" and self.request.user.is_authenticated:
            return "Estás viendo solo las noticias que marcaste como malas"

        # Majority opinion filters
        elif filter_param == "buena_mayoria":
            return "Estás viendo las noticias que la mayoría considera buenas"
        elif filter_param == "mala_mayoria":
            return "Estás viendo las noticias que la mayoría considera malas"

        # Entity filters
        elif filter_param.startswith("mencionan_") and entidad_id:
            try:
                from core.models import Entidad

                entidad = Entidad.objects.get(id=entidad_id)

                if filter_param == "mencionan_a":
                    return f"Estás viendo las noticias que mencionan a {entidad.nombre}"
                elif filter_param == "mencionan_positiva":
                    return f"Estás viendo las noticias que mencionan positivamente a {entidad.nombre}"
                elif filter_param == "mencionan_negativa":
                    return f"Estás viendo las noticias que mencionan negativamente a {entidad.nombre}"
            except (Entidad.DoesNotExist, ValueError):
                return "Estás viendo noticias filtradas por entidad"

        from core.tasks import refresh_proxy_list
        refresh_proxy_list.delay()

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

        if filter_param == "buena_mi" and self.request.user.is_authenticated:
            # Filter by good news by this user.
            queryset = queryset.filter(
                votos__usuario=self.request.user, votos__opinion="buena"
            )
        elif filter_param == "mala_mi" and self.request.user.is_authenticated:
            # Filter by bad news by this user.
            queryset = queryset.filter(
                votos__usuario=self.request.user, votos__opinion="mala"
            )
        elif filter_param == "buena_mayoria":
            # Filter by news with a majority of good votes.
            queryset = queryset.annotate(
                good_count=Count("votos", filter=Q(votos__opinion="buena"))
            ).filter(good_count__gt=F("votos__count") / 2)
        elif filter_param == "mala_mayoria":
            # Filter by news with a majority of bad votes.
            queryset = queryset.annotate(
                bad_count=Count("votos", filter=Q(votos__opinion="mala"))
            ).filter(bad_count__gt=F("votos__count") / 2)
        # Entity filters
        elif filter_param == "mencionan_a" and entidad_id:
            # Filter by news that mention the entity
            queryset = queryset.filter(entidades__entidad__pk=entidad_id)
        elif filter_param == "mencionan_positiva" and entidad_id:
            # Filter by news that mention the entity positively
            queryset = queryset.filter(
                entidades__entidad__pk=entidad_id, entidades__sentimiento="positivo"
            )
        elif filter_param == "mencionan_negativa" and entidad_id:
            # Filter by news that mention the entity negatively
            queryset = queryset.filter(
                entidades__entidad__pk=entidad_id, entidades__sentimiento="negativo"
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Only include the form in the initial full-page load.
        if not self.request.headers.get("HX-Request"):
            context["form"] = NoticiaForm()

        # Add filter description to context
        context["filter_description"] = self.get_filter_description()
        context["entidades"] = Entidad.objects.all()
        return context

    def render_to_response(self, context, **response_kwargs):
        # If the request is via HTMX, return just the list items partial.
        if self.request.headers.get("HX-Request"):
            self.template_name = "noticias/timeline_items.html"

            # When loading just the items via HTMX, we need to update the active filters section too
            if self.request.headers.get("HX-Target") == "timeline-items":
                # Add an HX-Trigger to update the active filters
                response_kwargs.setdefault("headers", {})
                response_kwargs["headers"]["HX-Trigger"] = (
                    '{"updateActiveFilters": {"description": "'
                    + context["filter_description"]
                    + '"}}'
                )
        return super().render_to_response(context, **response_kwargs)


class VoteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        noticia = get_object_or_404(Noticia, pk=pk)
        opinion = request.POST.get("opinion")
        if opinion not in ["buena", "mala", "neutral"]:
            return HttpResponseBadRequest("Invalid vote")

        # Update or create the vote for this user.
        # (This allows a user to change their vote.)
        Voto.objects.update_or_create(
            usuario=request.user, noticia=noticia, defaults={"opinion": opinion}
        )
        # Render the updated vote area partial.
        context = {"noticia": noticia, "user": request.user}
        return render(request, "noticias/vote_area.html", context)


class NoticiaCreateView(LoginRequiredMixin, FormView):
    template_name = "noticias/timeline_fragment.html"  # This fragment includes both the form and the timeline
    form_class = NoticiaForm
    success_url = reverse_lazy("timeline")

    def form_valid(self, form):
        vote_opinion = form.cleaned_data.get("opinion")
        enlace = form.cleaned_data.get("enlace")

        try:
            # Try to retrieve an existing Noticia with this enlace.
            noticia = Noticia.objects.get(enlace=enlace)
            noticia.update_title_image_from_archive()
            # Update or create the vote for the current user.
            Voto.objects.update_or_create(
                usuario=self.request.user,
                noticia=noticia,
                defaults={"opinion": vote_opinion},
            )
            noticia.find_archived()
        except Noticia.DoesNotExist:
            # Create a new Noticia if it doesn't exist.
            noticia = Noticia(
                agregado_por=self.request.user,
                enlace=enlace,
            )
            noticia.save()
            noticia.update_title_image_from_original_url()
            Voto.objects.create(
                usuario=self.request.user,
                noticia=noticia,
                opinion=vote_opinion,
            )
            noticia.find_archived()

        # For HTMX requests, re-render the entire timeline fragment (form and timeline).
        if self.request.headers.get("HX-Request"):
            noticias = Noticia.objects.all().order_by("-fecha_agregado")
            # Pass a fresh form instance so the fields are cleared.
            response = render(
                self.request,
                "noticias/timeline_fragment.html",
                {
                    "noticias": noticias,
                    "form": self.get_form_class()(),
                    "filter_description": "Estás viendo todas las noticias",
                },
            )
            # Add HTMX response headers
            response["HX-Trigger"] = (
                '{"noticiaCreated": {"message": "Noticia guardada exitosamente"}}'
            )
            return response
        return redirect(self.success_url)
        
    def form_invalid(self, form):
        # For HTMX requests, return the form with errors and trigger an error notification
        if self.request.headers.get("HX-Request"):
            # Get the first error message from the form
            errors = form.errors
            error_message = next(iter(errors.values()))[0] if errors else "Ha ocurrido un error al procesar el formulario"
            
            # Log the error for debugging
            logger.error(f"Form validation error: {errors}")
            
            # Render the form with errors
            response = render(
                self.request,
                self.template_name,
                {
                    "form": form,
                    "filter_description": "Estás viendo todas las noticias",
                    "noticias": Noticia.objects.all().order_by("-fecha_agregado"),
                },
            )
            
            # Add HTMX trigger for error notification
            response["HX-Trigger"] = f'{{"noticiaError": {{"message": "{error_message}"}}}}'
            return response
            
        # For non-HTMX requests, use the default behavior
        return super().form_invalid(form)


class RefreshNoticiaView(LoginRequiredMixin, View):
    def post(self, request, pk):
        noticia = get_object_or_404(Noticia, pk=pk)
        noticia.find_archived()
        noticia.update_title_image_from_archive()
        # Render the updated timeline item fragment.
        return render(request, "noticias/timeline_item.html", {"noticia": noticia})


class DeleteNoticiaView(LoginRequiredMixin, View):
    def post(self, request, pk):
        noticia = get_object_or_404(Noticia, pk=pk)
        noticia.delete()
        # Redirect to the main timeline page after deletion
        return redirect(reverse_lazy("timeline"))
