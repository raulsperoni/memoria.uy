"""Descarta proposiciones publicadas que repiten otra de la misma historia.

Se quedan primero las que tienen votos o están en una jornada, después las más
viejas. Las que tienen votos o jornada nunca se descartan. Sin --aplicar solo
muestra lo que haría (las decisiones de Jev igual se guardan en caché).
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Q

from archivo.models import Historia
from archivo.pipeline import UMBRAL_MISMA_PROPOSICION
from archivo.providers.decide import decidir


class Command(BaseCommand):
    help = "Descarta proposiciones duplicadas dentro de cada historia"

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Guardar los cambios")

    def handle(self, *args, aplicar=False, **opts):
        umbral = UMBRAL_MISMA_PROPOSICION()
        total = 0
        historias = Historia.objects.annotate(
            n=Count("proposiciones", filter=Q(proposiciones__estado="publicada"))
        ).filter(n__gt=1)
        for h in historias:
            props = list(
                h.proposiciones.filter(estado="publicada").annotate(
                    usada=Count("votos", distinct=True) + Count("jornadas", distinct=True)
                )
            )
            props.sort(key=lambda p: (p.usada == 0, p.pk))
            quedan = []
            for p in props:
                repite = None
                if not p.usada:
                    for q in quedan:
                        a, b = sorted([p.texto, q.texto])
                        if decidir("misma_proposicion", {"A": a, "B": b}) >= umbral:
                            repite = q
                            break
                if repite is None:
                    quedan.append(p)
                    continue
                total += 1
                self.stdout.write(f"h{h.pk} #{p.pk} repite #{repite.pk}: {p.texto[:100]}")
                if aplicar:
                    p.estado = "descartada"
                    p.save(update_fields=["estado"])
        verbo = "Descartadas" if aplicar else "Se descartarían"
        self.stdout.write(self.style.SUCCESS(f"{verbo}: {total}"))
