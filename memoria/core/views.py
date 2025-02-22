# views.py

from django.views.generic import ListView, View, CreateView
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponseBadRequest
from django.contrib.auth.mixins import LoginRequiredMixin
from core.models import Noticia, Voto
from core.forms import NoticiaForm
from django.urls import reverse_lazy


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


class NoticiaCreateView(LoginRequiredMixin, CreateView):
    model = Noticia
    form_class = NoticiaForm
    success_url = reverse_lazy("timeline")

    def form_valid(self, form):
        # Set the creator of the news item.
        form.instance.agregado_por = self.request.user
        response = super().form_valid(form)
        # Automatically create a vote by the creator with opinion "buena"
        Voto.objects.create(
            usuario=self.request.user, noticia=self.object, opinion="buena"
        )
        if self.request.headers.get("HX-Request"):
            noticias = Noticia.objects.all().order_by("-fecha_agregado")
            # Render the full timeline fragment, which includes the form.
            return render(
                self.request,
                "noticias/timeline_fragment.html",
                ***REMOVED***"noticias": noticias, "form": self.form_class()***REMOVED***,
            )

        return response
