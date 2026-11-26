"""Muestra cómo se reparten las similitudes entre historias y sus anteriores,
para elegir SIM_HISTORIA_PREVIA («Esta historia viene de»). Solo lee.

    manage.py calibrar_previas
    manage.py calibrar_previas --dias 60 --n 300 --pares 4
    manage.py calibrar_previas --umbral 0.62      # todos los pares sobre 0.62

Mirá los pares de cada franja y elegí el umbral donde dejan de ser la misma
trama. Después: SIM_HISTORIA_PREVIA=<valor> en web.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from archivo.views import DIAS_PREVIAS, SIM_PREVIA, _historias_publicas, ranking_previas

FRANJAS = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 1.01]
UMBRALES = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75]


def _corto(t, n=70):
    return t if len(t) <= n else t[: n - 1] + "…"


class Command(BaseCommand):
    help = "Reparto de similitudes entre historias y sus anteriores (para SIM_HISTORIA_PREVIA)"

    def add_arguments(self, parser):
        parser.add_argument("--dias", type=int, default=30, help="Historias de los últimos N días (default 30)")
        parser.add_argument("--n", type=int, default=200, help="Máximo de historias a mirar (default 200)")
        parser.add_argument("--pares", type=int, default=3, help="Pares de ejemplo por franja (default 3)")
        parser.add_argument("--umbral", type=float, default=None, help="Listar todos los pares sobre este valor")

    def handle(self, *args, dias, n, pares, umbral, **opts):
        desde = timezone.now() - timedelta(days=dias)
        historias = list(
            _historias_publicas().filter(primera_fuente_en__gte=desde).order_by("-n_medios", "-primera_fuente_en")[:n]
        )
        filas = []  # (historia, [(sim, previa), ...] top 3)
        for h in historias:
            top = ranking_previas(h)[:3]
            if top:
                filas.append((h, top))
        w = self.stdout.write
        w(f"{len(historias)} historias de los últimos {dias} días; {len(filas)} con anteriores "
          f"(ventana {DIAS_PREVIAS} días). Umbral actual: {SIM_PREVIA():.2f}\n")
        if not filas:
            return

        mejores = sorted(top[0][0] for _, top in filas)
        w("Mejor similitud de cada historia con una anterior:")
        w(f"  mín {mejores[0]:.2f} · mediana {mejores[len(mejores) // 2]:.2f} · máx {mejores[-1]:.2f}")
        maximo = max(1, max(sum(1 for m in mejores if a <= m < b) for a, b in zip(FRANJAS, FRANJAS[1:])))
        menos = sum(1 for m in mejores if m < FRANJAS[0])
        if menos:
            w(f"  <{FRANJAS[0]:.2f}     {menos:4d}")
        for a, b in zip(FRANJAS, FRANJAS[1:]):
            c = sum(1 for m in mejores if a <= m < b)
            w(f"  {a:.2f}–{min(b, 1):.2f} {c:4d} {'█' * round(30 * c / maximo)}")

        w("\nCon cada umbral, cuántas historias mostrarían «viene de» (y cuántas previas en promedio):")
        for u in UMBRALES:
            con = [sum(1 for s, _ in top if s >= u) for _, top in filas]
            k = sum(1 for x in con if x)
            prom = sum(con) / k if k else 0
            w(f"  {u:.2f}  {k:4d} de {len(historias)} ({100 * k / len(historias):.0f} %) · {prom:.1f} previas")

        todos = sorted(((s, h, p) for h, top in filas for s, p in top), key=lambda t: -t[0])
        if umbral is not None:
            w(f"\nTodos los pares ≥ {umbral:.2f}:")
            for s, h, p in todos:
                if s >= umbral:
                    self._par(s, h, p)
            return
        w("\nEjemplos por franja (¿es la misma trama?):")
        for a, b in reversed(list(zip(FRANJAS, FRANJAS[1:]))):
            ej = [t for t in todos if a <= t[0] < b][:pares]
            if ej:
                w(f"── {a:.2f}–{min(b, 1):.2f}")
                for s, h, p in ej:
                    self._par(s, h, p)

    def _par(self, s, h, p):
        self.stdout.write(
            f"  {s:.2f}  {h.primera_fuente_en:%d/%m} {_corto(h.titulo)}\n"
            f"        ← {p.primera_fuente_en:%d/%m} {_corto(p.titulo)}"
        )
