"""
URL configuration for memoria project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path, re_path
from django.views.generic import RedirectView

from core.sitemaps import CambioSitemap, EntidadSitemap, HistoriaSitemap, StaticViewSitemap
from core.views import AcercaDeView, PrivacidadView
from memoria.views import favicon, health_check, manifest, offline, robots_txt, service_worker

sitemaps = {
    "static": StaticViewSitemap,
    "historias": HistoriaSitemap,
    "entidades": EntidadSitemap,
    "cambios": CambioSitemap,
}

# Custom error handlers
handler500 = "core.error_handlers.server_error"

# Páginas del producto anterior (votar noticias): redirigen a su equivalente actual.
redirecciones_viejas = [
    re_path(r"^noticias/", RedirectView.as_view(url="/", permanent=True)),
    re_path(r"^bienvenida/$", RedirectView.as_view(url="/", permanent=True)),
    re_path(r"^mapa/$", RedirectView.as_view(url="/burbujas/", permanent=True)),
    re_path(r"^clusters/", RedirectView.as_view(url="/burbujas/", permanent=True)),
    re_path(r"^accounts/profile/$", RedirectView.as_view(url="/", permanent=False)),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("favicon.ico", favicon, name="favicon"),
    path("robots.txt", robots_txt, name="robots_txt"),
    path("manifest.webmanifest", manifest, name="manifest"),
    path("offline/", offline, name="offline"),
    path("sw.js", service_worker, name="service_worker"),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path("acerca-de/", AcercaDeView.as_view(), name="acerca_de"),
    path("privacidad/", PrivacidadView.as_view(), name="privacidad"),
    *redirecciones_viejas,
    path("", include("juego.urls")),
    path("", include("archivo.urls")),
    path("accounts/", include("allauth.urls")),
    path("__reload__/", include("django_browser_reload.urls")),
    path("health/", health_check, name="health_check"),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
