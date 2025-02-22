# views.py

from django.views.generic import ListView, View, FormView
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponseBadRequest
from django.contrib.auth.mixins import LoginRequiredMixin
from core.models import Noticia, Voto
from core.forms import NoticiaForm
from django.urls import reverse_lazy
from django.shortcuts import redirect


class NewsTimelineView(ListView):
    model = Noticia
    template_name = "noticias/timeline.html"
    context_object_name = "noticias"
    ordering = ["-fecha_agregado"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Provide an empty form for creating a new Noticia.
        context["form"] = NoticiaForm()
        return context


class VoteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        noticia = get_object_or_404(Noticia, pk=pk)
        opinion = request.POST.get("opinion")
        if opinion not in ["buena", "mala", "neutral"]:
            return HttpResponseBadRequest("Invalid vote")

        # Update or create the vote for this user.
        # (This allows a user to change their vote.)
        Voto.objects.update_or_create(
            usuario=request.user, noticia=noticia, defaults=***REMOVED***"opinion": opinion***REMOVED***
        )
        # Render the updated vote area partial.
        context = ***REMOVED***"noticia": noticia, "user": request.user***REMOVED***
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
            # Refresh its archive data.
            noticia.get_archive()
            noticia.save(
                update_fields=[
                    "archivo_url",
                    "archivo_fecha",
                    "archivo_imagen",
                    "titulo",
             ***REMOVED***
            )
            # Update or create the vote for the current user.
            Voto.objects.update_or_create(
                usuario=self.request.user,
                noticia=noticia,
                defaults=***REMOVED***"opinion": vote_opinion***REMOVED***,
            )
        except Noticia.DoesNotExist:
            # Create a new Noticia if it doesn't exist.
            noticia = Noticia(
                agregado_por=self.request.user,
                enlace=enlace,
            )
            noticia.get_archive()
            noticia.save()
            Voto.objects.create(
                usuario=self.request.user,
                noticia=noticia,
                opinion=vote_opinion,
            )

        # For HTMX requests, re-render the entire timeline fragment (form and timeline).
        if self.request.headers.get("HX-Request"):
            noticias = Noticia.objects.all().order_by("-fecha_agregado")
            # Pass a fresh form instance so the fields are cleared.
            return render(
                self.request,
                "noticias/timeline_fragment.html",
                ***REMOVED***"noticias": noticias, "form": self.get_form_class()()***REMOVED***,
            )
        return redirect(self.success_url)
