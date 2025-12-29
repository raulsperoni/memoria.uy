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
from django.urls import path, include
from core.views import (
    NewsTimelineView,
    VoteView,
    NoticiaCreateView,
    RefreshNoticiaView,
    DeleteNoticiaView,
)
from core.api_views import (
    SubmitFromExtensionView,
    CheckVoteView,
)
from memoria.views import health_check

urlpatterns = (
    [
        path("admin/", admin.site.urls),
        path("", NewsTimelineView.as_view(), name="timeline"),
        path("vote/<int:pk>/", VoteView.as_view(), name="vote"),
        path("noticias/new/", NoticiaCreateView.as_view(), name="noticia-create"),
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
        path("accounts/", include("allauth.urls")),
        path("__reload__/", include("django_browser_reload.urls")),
        path("health/", health_check, name="health_check"),
    ]
    + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
)
