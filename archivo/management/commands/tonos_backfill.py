"""Calcula el tono hacia las personas en notas ya procesadas.

Comparte el cupo diario con la tarea `tonos` del tick (MAX_TONOS_DIA, 500 por
defecto): el tick ya vacía la cola de a poco, nuevas primero. Esto sirve para
empujar a mano o para mirar qué queda.

    manage.py tonos_backfill --contar
    manage.py tonos_backfill --limite 100 --desde 2026-11-01
"""

from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from archivo.tonos import MAX_TONOS_DIA, calcular_tonos, tonos_hoy, tonos_pendientes


class Command(BaseCommand):
    help = "Calcula tonos pendientes respetando el cupo diario"

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=None, help="Máximo de llamadas al LLM")
        parser.add_argument("--desde", default=None, help="Solo notas publicadas desde AAAA-MM-DD")
        parser.add_argument("--contar", action="store_true", help="Solo mostrar cuántas faltan")

    def handle(self, *args, limite, desde, contar, **opts):
        if desde:
            desde = timezone.make_aware(datetime.strptime(desde, "%Y-%m-%d"))
        pendientes = tonos_pendientes(desde).count()
        self.stdout.write(f"pendientes={pendientes} hoy={tonos_hoy()}/{MAX_TONOS_DIA()}")
        if not contar:
            self.stdout.write(calcular_tonos(limite=limite, desde=desde))
