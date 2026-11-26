"""Admin de memoria.uy: mismo sitio de Django, con los modelos agrupados por
lo que hace el dueño (curar, vigilar) y un pulso del pipeline en el inicio."""

from datetime import timedelta

from django.contrib import admin
from django.contrib.admin.apps import AdminConfig
from django.urls import reverse
from django.utils import timezone

# (título, [(app_label, nombre del modelo en minúscula)])
GRUPOS = [
    ("Medios y fuentes", [("archivo", "medio"), ("archivo", "fuente"), ("archivo", "snapshot")]),
    (
        "Historias",
        [
            ("archivo", "historia"),
            ("archivo", "hecho"),
            ("archivo", "proposicion"),
            ("core", "entidad"),
        ],
    ),
    ("Tono y notas editadas", [("archivo", "tono"), ("archivo", "cambio")]),
    ("Pipeline", [("archivo", "decision"), ("archivo", "usoproveedor")]),
    (
        "Juego y burbujas",
        [
            ("juego", "jornada"),
            ("juego", "votoproposicion"),
            ("juego", "burbujarun"),
            ("juego", "burbuja"),
            ("juego", "burbujapatron"),
            ("juego", "burbujamiembro"),
        ],
    ),
]
GRUPO_CUENTAS = "Cuentas"


class MemoriaAdminSite(admin.AdminSite):
    site_header = "memoria.uy"
    site_title = "memoria.uy · admin"
    index_title = "Curar y vigilar"

    def get_app_list(self, request, app_label=None):
        apps = super().get_app_list(request, app_label)
        if app_label:
            return apps
        modelos = {}
        for app in apps:
            for m in app["models"]:
                modelos[(app["app_label"], m["object_name"].lower())] = m
        grupos = []
        for i, (nombre, claves) in enumerate(GRUPOS):
            models = [modelos.pop(c) for c in claves if c in modelos]
            if models:
                grupos.append(self._grupo(f"grupo{i}", nombre, models))
        if modelos:
            grupos.append(self._grupo("cuentas", GRUPO_CUENTAS, list(modelos.values())))
        return grupos

    @staticmethod
    def _grupo(clave, nombre, models):
        return {
            "name": nombre,
            "app_label": clave,
            "app_url": "",
            "has_module_perms": True,
            "models": models,
        }

    def index(self, request, extra_context=None):
        extra_context = {**(extra_context or {}), "pulso": self.pulso()}
        return super().index(request, extra_context)

    def pulso(self):
        """Conteos baratos para ver de un vistazo si el pipeline anda."""
        from django.db.models import Sum

        from archivo.models import Fuente, Historia, Proposicion, UsoProveedor
        from juego.models import Jornada

        def url(nombre, query=""):
            return reverse(f"admin:{nombre}_changelist") + query

        hoy = timezone.localdate()
        desde = timezone.now() - timedelta(hours=24)
        fuentes = Fuente.objects.filter(descubierta_en__gte=desde)
        jornada = Jornada.objects.filter(fecha=hoy).first()
        costo = UsoProveedor.objects.filter(fecha=hoy).aggregate(t=Sum("costo_usd"))["t"] or 0
        return [
            ("Fuentes en 24 h", fuentes.count(), url("archivo_fuente")),
            (
                "En error",
                Fuente.objects.filter(estado="error").count(),
                url("archivo_fuente", "?estado__exact=error"),
            ),
            (
                "Historias abiertas",
                Historia.objects.filter(estado="abierta").count(),
                url("archivo_historia", "?estado__exact=abierta"),
            ),
            (
                "Proposiciones candidatas",
                Proposicion.objects.filter(estado="candidata").count(),
                url("archivo_proposicion", "?estado__exact=candidata"),
            ),
            (
                "Jornada de hoy",
                "publicada" if jornada and jornada.publicada else ("sin publicar" if jornada else "no hay"),
                url("juego_jornada"),
            ),
            ("Costo hoy", f"US$ {costo:.2f}", url("archivo_usoproveedor")),
        ]


class MemoriaAdminConfig(AdminConfig):
    default_site = "core.admin_site.MemoriaAdminSite"
