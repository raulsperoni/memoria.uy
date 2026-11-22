from datetime import date

from django.core.management.base import BaseCommand

from juego.logica import armar_jornada


class Command(BaseCommand):
    help = "Arma (o muestra) la jornada del día."

    def add_arguments(self, parser):
        parser.add_argument("--fecha", help="AAAA-MM-DD (default: hoy)")

    def handle(self, *args, fecha=None, **opts):
        f = date.fromisoformat(fecha) if fecha else None
        j = armar_jornada(f)
        if not j:
            self.stderr.write("No hay suficientes proposiciones candidatas.")
            return
        self.stdout.write(str(j))
        for it in j.items_ordenados():
            p = it.proposicion
            self.stdout.write(f"  {it.orden + 1}. {p.texto}  [div {p.divisividad or 0:.2f}{' · recurrente' if it.recurrente else ''}]")
