from django.views.generic import TemplateView


class AcercaDeView(TemplateView):
    template_name = "acerca_de.html"

    def get_context_data(self, **kwargs):
        from core.decisiones import todas

        ctx = super().get_context_data(**kwargs)
        ctx["decisiones"] = list(reversed(todas()))
        return ctx


class PrivacidadView(TemplateView):
    template_name = "privacidad.html"
