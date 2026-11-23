"""Corre el pipeline completo sobre URLs concretas (prueba con proveedores reales).

    manage.py probar_archivo URL [URL ...] [--sin-filtro]
"""

from urllib.parse import urlparse

from django.core.management.base import BaseCommand
from django.utils import timezone

from archivo import pipeline
from archivo.models import Fuente, Medio, sha256
from core.utils import normalize_url


class Command(BaseCommand):
    help = "Corre descubrir→filtrar→extraer→agrupar→procesar sobre URLs dadas."

    def add_arguments(self, parser):
        parser.add_argument("urls", nargs="+")
        parser.add_argument("--sin-filtro", action="store_true")

    def handle(self, *args, urls, sin_filtro=False, **opts):
        historias = set()
        for url in urls:
            url = normalize_url(url)
            host = urlparse(url).netloc.lower().removeprefix("www.")
            medio = next((m for m in Medio.objects.all() if host.endswith(m.dominio)), None)
            if not medio:
                self.stderr.write(f"Sin medio para {host}; corré cargar_medios")
                continue
            f = Fuente.objects.filter(url_hash=sha256(url)).first() or Fuente.objects.create(
                medio=medio, url=url, publicada_en=timezone.now()
            )
            if f.estado == "descartada" and not sin_filtro:
                self.stdout.write(f"[filtro] descartada antes: {f.motivo_descarte} · {f.titulo[:70]}")
                continue
            if not sin_filtro and f.estado == "descubierta":
                if not f.titulo:
                    # Sin RSS no hay título: lo inferimos del slug.
                    f.titulo = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1].replace("-", " ")
                    f.save(update_fields=["titulo"])
                ok = pipeline.filtrar(f)
                self.stdout.write(f"[filtro] {f.interes:.2f} {'✓' if ok else '✗'} {f.titulo[:70]}")
                if not ok:
                    continue
            if f.estado in ("descubierta", "error"):
                f.estado = "descubierta"
                if not pipeline.extraer(f, respetar_cupo=False):
                    self.stderr.write(f"[extraer] falló {url}: {f.motivo_descarte}")
                    continue
                self.stdout.write(f"[extraer] {len(f.texto)} chars · {f.titulo[:70]}")
            h = f.historia or pipeline.agrupar(f)
            self.stdout.write(f"[agrupar] historia #{h.pk} ({h.n_medios} medios)")
            historias.add(h.pk)

        from archivo.models import Historia

        for h in Historia.objects.filter(pk__in=historias):
            h.refresh_from_db()
            ok = pipeline.procesar_historia(h)
            h.refresh_from_db()
            self.stdout.write(self.style.SUCCESS(f"\n=== Historia #{h.pk}: {h.titulo or '(no procesada)'} ==="))
            if not ok:
                self.stdout.write(f"no procesada (relevancia {h.relevancia})")
                continue
            self.stdout.write(f"{h.categoria} · {h.n_medios} medios\n{h.resumen}\n")
            for hecho in h.hechos.all():
                medios = ", ".join(
                    f"{hf.fuente.medio.nombre} ({hf.fiel:.2f})" for hf in hecho.hechofuente_set.all()
                )
                self.stdout.write(f"  • {hecho.texto}\n    ← {medios}")
            for p in h.proposiciones.all():
                self.stdout.write(
                    f"  ¿? {p.texto}  [{p.estado}, calidad {p.calidad:.2f}, divisividad {p.divisividad:.2f}, tema {p.tema}]"
                )
            ents = sorted({e.nombre for hh in h.hechos.all() for e in hh.entidades.all()})
            self.stdout.write(f"  entidades: {', '.join(ents)}")
