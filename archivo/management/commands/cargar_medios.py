from django.core.management.base import BaseCommand

from archivo.medios_iniciales import EXCLUIDAS_COMUNES, MEDIOS
from archivo.models import Medio


class Command(BaseCommand):
    help = "Crea/actualiza los medios iniciales (no pisa feeds ya cargados)."

    def handle(self, *args, **opts):
        for m in MEDIOS:
            datos = dict(m)
            datos.setdefault("secciones_excluidas", EXCLUIDAS_COMUNES)
            obj, creado = Medio.objects.get_or_create(dominio=datos["dominio"], defaults=datos)
            self.stdout.write(f"{'+' if creado else '='} {obj.nombre}")
