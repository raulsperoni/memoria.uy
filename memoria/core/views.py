# views.py

from django.views.generic import ListView, View, FormView
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponseBadRequest
from django.contrib.auth.mixins import LoginRequiredMixin
from core.models import Noticia, Voto
from core.forms import NoticiaForm
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.db.models import Count, Q, F


class NewsTimelineView(ListView):
    model = Noticia
    template_name = "noticias/timeline.html"
    context_object_name = "noticias"
    ordering = ["-fecha_agregado"]
    paginate_by = 10  # Adjust the number as needed

    def get_queryset(self):
        queryset = super().get_queryset()
        filter_param = self.request.GET.get("filter")
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
        # You can add additional filter conditions here as the filter bar grows.
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Only include the form in the initial full-page load.
        if not self.request.headers.get("HX-Request"):
            context["form"] = NoticiaForm()
        return context

    def render_to_response(self, context, **response_kwargs):
        # If the request is via HTMX, return just the list items partial.
        if self.request.headers.get("HX-Request"):
            self.template_name = "noticias/timeline_items.html"
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
            return render(
                self.request,
                "noticias/timeline_fragment.html",
                {"noticias": noticias, "form": self.get_form_class()()},
            )
        return redirect(self.success_url)


class RefreshNoticiaView(LoginRequiredMixin, View):
    def post(self, request, pk):
        noticia = get_object_or_404(Noticia, pk=pk)
        noticia.find_archived()
        noticia.update_title_image_from_archive()
        # Render the updated timeline item fragment.
        return render(request, "noticias/timeline_item.html", {"noticia": noticia})
