from django.views.generic import TemplateView


class AcercaDeView(TemplateView):
    template_name = "acerca_de.html"


class PrivacidadView(TemplateView):
    template_name = "privacidad.html"
