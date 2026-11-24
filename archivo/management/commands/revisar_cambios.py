"""Revisa las notas editadas ya registradas con las reglas actuales.

Borra los cambios de cuerpo que no son ediciones reales: capturas recortadas
(muro de pago), capturas que completan una anterior recortada, o bloques de
titulares de otras notas del medio. En los recortes, la nota vuelve a tener el
texto completo. Sin --aplicar solo muestra lo que haría.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from archivo.models import Cambio
from archivo.pipeline import clasificar_cambio_cuerpo


def textos(diff):
    antes = " ".join(t for op, t in diff if op in ("=", "-"))
    despues = " ".join(t for op, t in diff if op in ("=", "+"))
    return antes, despues


class Command(BaseCommand):
    help = "Borra notas editadas que no son ediciones reales"

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Guardar los cambios")

    def handle(self, *args, aplicar=False, **opts):
        conteo = {}
        for c in Cambio.objects.filter(tipo="cuerpo").select_related("fuente__medio").order_by("pk"):
            antes, despues = textos(c.diff)
            clase = clasificar_cambio_cuerpo(antes, despues, c.fuente)
            conteo[clase] = conteo.get(clase, 0) + 1
            if clase == "real":
                continue
            self.stdout.write(f"#{c.pk} {c.fuente.medio.nombre}: {clase} · {c.fuente.titulo[:80]}")
            if not aplicar:
                continue
            with transaction.atomic():
                f = c.fuente
                if clase == "recorte" and f.ultimo_snapshot_id == c.despues_id:
                    f.texto = antes
                    f.ultimo_snapshot_id = c.antes_id
                    f.save(update_fields=["texto", "ultimo_snapshot"])
                c.delete()
        verbo = "Borrados" if aplicar else "Se borrarían"
        no_reales = sum(n for k, n in conteo.items() if k != "real")
        self.stdout.write(self.style.SUCCESS(f"{verbo}: {no_reales} · por clase: {conteo}"))
