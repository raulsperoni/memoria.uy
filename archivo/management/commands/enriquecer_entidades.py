"""Fichas de entidades con Wikidata y Wikipedia.

Comparte el cupo diario con la tarea `fichas` del tick (MAX_ENRIQUECIMIENTOS_DIA).

    manage.py enriquecer_entidades --contar
    manage.py enriquecer_entidades --limite 20
    manage.py enriquecer_entidades --entidad 123          # una, sin cupo
    manage.py enriquecer_entidades --fijar 123 Q1234      # staff: corrige el QID
    manage.py enriquecer_entidades --anular 123           # staff: que no tenga ficha
"""

from django.core.management.base import BaseCommand, CommandError

from archivo.entidades_wikidata import (
    MAX_DIA,
    enriquecer,
    enriquecer_pendientes,
    enriquecimientos_hoy,
    entidades_pendientes,
    fijar as fijar_qid,
)
from core.models import Entidad


class Command(BaseCommand):
    help = "Busca o refresca la ficha de Wikidata/Wikipedia de las entidades"

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=None, help="Máximo de entidades")
        parser.add_argument("--contar", action="store_true", help="Solo mostrar cuántas faltan")
        parser.add_argument("--entidad", type=int, help="Id de una entidad (ignora el cupo)")
        parser.add_argument("--fijar", nargs=2, metavar=("ID", "QID"), help="Staff: asocia un QID y no se vuelve a buscar")
        parser.add_argument("--anular", type=int, metavar="ID", help="Staff: sin ficha, no se vuelve a buscar")

    def _entidad(self, pk):
        try:
            return Entidad.objects.get(pk=int(pk))
        except (Entidad.DoesNotExist, ValueError):
            raise CommandError(f"No existe la entidad {pk}")

    def handle(self, *args, limite, contar, entidad, fijar, anular, **opts):
        if anular:
            self.stdout.write(fijar_qid(self._entidad(anular), ""))
            return
        if fijar:
            try:
                self.stdout.write(fijar_qid(self._entidad(fijar[0]), fijar[1]))
            except ValueError as e:
                raise CommandError(str(e))
            return
        if entidad:
            self.stdout.write(enriquecer(self._entidad(entidad)))
            return
        self.stdout.write(f"pendientes={entidades_pendientes().count()} hoy={enriquecimientos_hoy()}/{MAX_DIA()}")
        if not contar:
            self.stdout.write(enriquecer_pendientes(limite=limite))
