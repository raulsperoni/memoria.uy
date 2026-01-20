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
from django.urls import path, include
from core.sitemaps import NoticiaSitemap, StaticViewSitemap
from core.views import (
    NewsTimelineView,
    VoteView,
    NoticiaCreateView,
    RefreshNoticiaView,
    DeleteNoticiaView,
    AcercaDeView,
    PrivacidadView,
    BienvenidaView,
    NoticiaDetailView,
)
from core.api_views import (
    SubmitFromExtensionView,
    CheckVoteView,
)
from core.api_clustering import (
    cluster_data,
    voter_cluster_membership,
    cluster_voting_patterns,
    trigger_clustering,
)
from core.views_clustering import (
    ClusterVisualizationView,
    ClusterStatsView,
    ClusterReportView,
    cluster_data_json,
    cluster_evolution_json,
    cluster_og_image,
    upload_cluster_og_image,
    consensus_data_json,
    bridges_data_json,
    polarization_timeline_json,
    cluster_stability_json,
)
from memoria.views import health_check, robots_txt, favicon

# Sitemap configuration
sitemaps = {
    "noticias": NoticiaSitemap,
    "static": StaticViewSitemap,
}

# Custom error handlers
handler500 = "core.error_handlers.server_error"
handler429 = "core.error_handlers.ratelimited_error"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("favicon.ico", favicon, name="favicon"),
    path("robots.txt", robots_txt, name="robots_txt"),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path("", NewsTimelineView.as_view(), name="timeline"),
    path("acerca-de/", AcercaDeView.as_view(), name="acerca_de"),
    path("privacidad/", PrivacidadView.as_view(), name="privacidad"),
    path("bienvenida/", BienvenidaView.as_view(), name="bienvenida"),
    path("vote/<int:pk>/", VoteView.as_view(), name="vote"),
    path("noticias/new/", NoticiaCreateView.as_view(), name="noticia-create"),
    path(
        "noticias/<slug:slug>/",
        NoticiaDetailView.as_view(),
        name="noticia-detail",
    ),
    path(
        "noticias/<int:pk>/refresh/",
        RefreshNoticiaView.as_view(),
        name="noticia-refresh",
    ),
    path(
        "noticias/<int:pk>/delete/",
        DeleteNoticiaView.as_view(),
        name="noticia-delete",
    ),
    # Extension API endpoints
    path(
        "api/submit-from-extension/",
        SubmitFromExtensionView.as_view(),
        name="api-submit-extension",
    ),
    path(
        "api/check-vote/",
        CheckVoteView.as_view(),
        name="api-check-vote",
    ),
    # Clustering API endpoints
    path(
        "api/clustering/data/",
        cluster_data,
        name="api-cluster-data",
    ),
    path(
        "api/clustering/voter/me/",
        voter_cluster_membership,
        name="api-voter-cluster",
    ),
    path(
        "api/clustering/clusters/<int:cluster_id>/votes/",
        cluster_voting_patterns,
        name="api-cluster-votes",
    ),
    path(
        "api/clustering/trigger/",
        trigger_clustering,
        name="api-trigger-clustering",
    ),
    path(
        "api/clustering/data/json/",
        cluster_data_json,
        name="api-cluster-data-json",
    ),
    path(
        "api/clustering/evolution/",
        cluster_evolution_json,
        name="api-cluster-evolution",
    ),
    path(
        "api/mapa/og-image/",
        cluster_og_image,
        name="api-cluster-og-image",
    ),
    path(
        "api/mapa/upload-og-image/",
        upload_cluster_og_image,
        name="api-upload-cluster-og-image",
    ),
    # New clustering analysis APIs
    path(
        "api/clustering/consensus/",
        consensus_data_json,
        name="api-consensus-data",
    ),
    path(
        "api/clustering/bridges/",
        bridges_data_json,
        name="api-bridges-data",
    ),
    path(
        "api/clustering/polarization-timeline/",
        polarization_timeline_json,
        name="api-polarization-timeline",
    ),
    path(
        "api/clustering/stability/",
        cluster_stability_json,
        name="api-cluster-stability",
    ),
    # Clustering UI endpoint - mapa de burbujas
    path(
        "mapa/",
        ClusterVisualizationView.as_view(),
        name="mapa",
    ),
    path(
        "clusters/stats/",
        ClusterStatsView.as_view(),
        name="cluster-stats",
    ),
    path(
        "clusters/report/",
        ClusterReportView.as_view(),
        name="cluster-report",
    ),
    path("accounts/", include("allauth.urls")),
    path("__reload__/", include("django_browser_reload.urls")),
    path("health/", health_check, name="health_check"),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
