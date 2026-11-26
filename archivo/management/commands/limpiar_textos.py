"""Saca de las notas ya guardadas las líneas que su medio repite en todas
(avisos de suscripción, muro de pago) y reagrupa las notas que habían quedado
en una historia por culpa de esas líneas.

    manage.py limpiar_textos                 # muestra qué haría, no guarda nada
    manage.py limpiar_textos --medio busqueda --dias 14
    manage.py limpiar_textos --aplicar

Solo se reagrupan las notas cuyo texto para comparar cambió (el aviso era su
primer párrafo). Si siguen en su historia lo decide Jev («¿mismo hecho?»
contra hasta 3 notas sanas de la historia), igual que al agrupar.
"""

from collections import defaultdict
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from archivo import pipeline
from archivo.limpieza import detectar, limpiar
from archivo.models import Fuente, Historia, Medio
from archivo.providers import get_embedder
from archivo.providers.decide import decidir


def _centroide(embs):
    if not embs:
        return []
    c = [sum(xs) / len(embs) for xs in zip(*embs)]
    norma = sum(x * x for x in c) ** 0.5 or 1.0
    return [x / norma for x in c]


def _corto(t, n=75):
    return t if len(t) <= n else t[: n - 1] + "…"


def _mismo_hecho(a, b):
    return decidir(
        "mismo_hecho",
        {
            "A": {"titulo": a.titulo, "texto": (a.texto or a.bajada)[:800]},
            "B": {"titulo": b.titulo, "texto": (b.texto or b.bajada)[:800]},
        },
    ) >= 0.5


class Command(BaseCommand):
    help = "Limpia el texto repetido de cada medio en notas ya guardadas y reagrupa las afectadas"

    def add_arguments(self, parser):
        parser.add_argument("--medio", help="Slug del medio (default: todos)")
        parser.add_argument("--dias", type=int, default=14, help="Notas publicadas en los últimos N días (default 14)")
        parser.add_argument("--aplicar", action="store_true", help="Guardar los cambios")

    def handle(self, *args, medio, dias, aplicar, **opts):
        with transaction.atomic():
            self._correr(medio, dias, aplicar)
            if not aplicar:
                # La vista previa también consulta a Jev; no dejamos ni su caché.
                transaction.set_rollback(True)

    def _correr(self, medio, dias, aplicar):
        w = self.stdout.write
        medios = Medio.objects.filter(slug=medio) if medio else Medio.objects.filter(activo=True)
        desde = timezone.now() - timedelta(days=dias)
        limpias, reagrupar = [], []
        for m in medios:
            lineas = set(m.lineas_repetidas or []) | set(detectar(m))
            if not lineas:
                continue
            m.lineas_repetidas = sorted(lineas)
            m.save(update_fields=["lineas_repetidas"])
            n = 0
            for f in Fuente.objects.filter(medio=m, publicada_en__gte=desde).exclude(texto=""):
                limpio = limpiar(f.texto, lineas)
                if limpio == f.texto:
                    continue
                antes = pipeline._texto_para_embedding(f)
                f.texto = limpio
                limpias.append(f)
                n += 1
                if pipeline._texto_para_embedding(f) != antes and f.historia_id:
                    reagrupar.append(f)
            w(f"\n{m.nombre}: {len(lineas)} líneas repetidas, {n} notas con ellas")
            for linea in sorted(lineas)[:12]:
                w(f"  · {_corto(linea, 100)}")
        w(f"\n{len(limpias)} notas se limpian; en {len(reagrupar)} cambia el texto con el que se agrupan.")
        if not limpias:
            return

        tocadas = {f.pk for f in reagrupar}
        por_historia = defaultdict(list)
        for f in reagrupar:
            por_historia[f.historia_id].append(f)
        salen = []
        w("\nPor historia (siguen / salen):")
        for hid, fs in por_historia.items():
            h = Historia.objects.get(pk=hid)
            # Hasta 3 notas sanas de referencia: la historia puede tener más de
            # un ángulo. Sigue si es el mismo hecho que alguna.
            sanas = list(h.fuentes.exclude(pk__in=tocadas).exclude(texto="").order_by("publicada_en")[:3])
            if not sanas:  # todas tenían el aviso: la primera hace de referencia
                sanas, fs = [fs[0]], fs[1:]
            fuera = [f for f in fs if not any(_mismo_hecho(s, f) for s in sanas)]
            salen += fuera
            w(f"  h{hid} «{_corto(h.titulo, 60)}»: {len(fs) - len(fuera)} / {len(fuera)}")
            for f in fuera:
                w(f"      − {_corto(f.titulo)}")
        w(f"\nSalen {len(salen)} notas de su historia.")

        if not aplicar:
            w("Sin --aplicar no se guardó nada.")
            return

        nuevos = get_embedder().embed([pipeline._texto_para_embedding(f) for f in reagrupar]) if reagrupar else []
        embedding = {f.pk: e for f, e in zip(reagrupar, nuevos)}
        for f in limpias:
            campos = ["texto"]
            if f.pk in embedding:
                f.embedding = embedding[f.pk]
                campos.append("embedding")
            if f in salen:
                f.historia = None
                f.estado = "extraida"
                campos += ["historia", "estado"]
            f.save(update_fields=campos)
        for hid in por_historia:
            h = Historia.objects.get(pk=hid)
            restantes = list(h.fuentes.all())
            embs = [x.embedding for x in restantes if x.embedding]
            h.centroide = _centroide(embs)
            h.n_embeddings = len(embs)
            fechas = [x.publicada_en for x in restantes if x.publicada_en]
            if fechas:
                h.ultima_fuente_en = max(fechas)
            h.recalcular_n_medios()
            h.save()
        # Las que perdieron notas se vuelven a procesar (título, hechos, frases).
        perdieron = {hid for hid, fs in por_historia.items() if any(f in salen for f in fs)}
        Fuente.objects.filter(historia_id__in=perdieron).update(estado="extraida")
        n = sum(1 for f in salen if pipeline.agrupar(f))
        w(f"Listo: {len(limpias)} notas limpias, {len(salen)} reagrupadas ({n} con historia), "
          f"{len(perdieron)} historias se reprocesan en el próximo tick.")
