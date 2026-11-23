"""
Burbujas de opinión sobre proposiciones, reutilizando el motor matemático de
core/clustering (PCA sparsity-aware + agrupamiento con silhouette, à la Polis).

Votos: acuerdo = +1, desacuerdo = −1, no sé = ε. Ver docs/SCIENTIFIC.md.
"""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from datetime import timedelta

import numpy as np
from django.db import transaction
from django.utils import timezone
from scipy.sparse import lil_matrix

from core.clustering import compute_silhouette_score, compute_sparsity_aware_pca, group_clusters

from .models import Burbuja, BurbujaMiembro, BurbujaPatron, BurbujaRun, VotoProposicion

logger = logging.getLogger(__name__)

EPS = 0.0001
CODIGO = {"acuerdo": 1.0, "desacuerdo": -1.0, "nose": EPS}
MIN_OPINAN_PATRON = 3  # opiniones mínimas de una burbuja para considerar su patrón
UMBRAL_CONSENSO = 60  # % : todas las burbujas ≥ 60 % de acuerdo (o ≤ 40 %)


def _clave(v):
    return ("u", v["usuario_id"]) if v["usuario_id"] else ("s", v["session_key"])


def construir_matriz(dias=60, min_votos=5):
    desde = timezone.now() - timedelta(days=dias)
    votos = list(
        VotoProposicion.objects.filter(creado_en__gte=desde, proposicion__estado="publicada").values(
            "usuario_id", "session_key", "proposicion_id", "opinion"
        )
    )
    por_votante = defaultdict(list)
    for v in votos:
        por_votante[_clave(v)].append(v)
    votantes = sorted(k for k, vs in por_votante.items() if len(vs) >= min_votos)
    props = sorted({v["proposicion_id"] for k in votantes for v in por_votante[k]})
    iv = {k: i for i, k in enumerate(votantes)}
    ip = {p: j for j, p in enumerate(props)}
    m = lil_matrix((len(votantes), len(props)), dtype=np.float32)
    for k in votantes:
        for v in por_votante[k]:
            m[iv[k], ip[v["proposicion_id"]]] = CODIGO[v["opinion"]]
    return m, votantes, props, por_votante


def calcular_burbujas(dias=60, min_votos=5, min_votantes=None, nombrar=True) -> BurbujaRun:
    min_votantes = min_votantes or int(os.environ.get("BURBUJAS_MIN_VOTANTES", 50))
    params = {"dias": dias, "min_votos": min_votos, "min_votantes": min_votantes}
    m, votantes, props, por_votante = construir_matriz(dias, min_votos)
    if len(votantes) < min_votantes or len(props) < 3:
        return BurbujaRun.objects.create(
            estado="insuficiente",
            n_votantes=len(votantes),
            n_proposiciones=len(props),
            parametros=params,
            mensaje=f"{len(votantes)} votantes con ≥{min_votos} votos (mínimo {min_votantes})",
        )

    pca = compute_sparsity_aware_pca(m, n_components=2)
    proy = np.asarray(pca["voter_projections"])
    labels, k, _ = group_clusters(None, proy, k_range=(2, 5))
    labels = np.asarray(labels)
    sil = compute_silhouette_score(proy, labels) if k > 1 else None

    with transaction.atomic():
        run = BurbujaRun.objects.create(
            n_votantes=len(votantes),
            n_proposiciones=len(props),
            k=int(k),
            silhouette=float(sil) if sil is not None else None,
            varianza=[float(x) for x in pca.get("variance_explained", [])],
            parametros=params,
        )
        # Numeramos burbujas por tamaño (A = la más grande)
        orden = sorted(set(labels.tolist()), key=lambda g: -int((labels == g).sum()))
        burbujas = {}
        for n, g in enumerate(orden):
            idx = labels == g
            burbujas[g] = Burbuja.objects.create(
                run=run,
                numero=n,
                tamano=int(idx.sum()),
                cx=float(proy[idx, 0].mean()),
                cy=float(proy[idx, 1].mean()),
            )
        miembros, conteos = [], defaultdict(lambda: [0, 0, 0])
        for i, clave in enumerate(votantes):
            b = burbujas[labels[i]]
            tipo, ident = clave
            miembros.append(
                BurbujaMiembro(
                    run=run,
                    burbuja=b,
                    usuario_id=ident if tipo == "u" else None,
                    session_key=ident if tipo == "s" else None,
                    x=float(proy[i, 0]),
                    y=float(proy[i, 1]),
                )
            )
            for v in por_votante[clave]:
                c = conteos[(b.pk, v["proposicion_id"])]
                c[{"acuerdo": 0, "desacuerdo": 1, "nose": 2}[v["opinion"]]] += 1
        BurbujaMiembro.objects.bulk_create(miembros, batch_size=1000)
        BurbujaPatron.objects.bulk_create(
            [
                BurbujaPatron(run=run, burbuja_id=bid, proposicion_id=pid, acuerdo=a, desacuerdo=d, nose=n)
                for (bid, pid), (a, d, n) in conteos.items()
            ],
            batch_size=1000,
        )
    if nombrar:
        try:
            nombrar_burbujas(run)
        except Exception:
            logger.exception("No se pudieron nombrar las burbujas")
    return run


# ---------------------------------------------------------------------------
# Lecturas
# ---------------------------------------------------------------------------


def ultimo_run():
    return BurbujaRun.objects.filter(estado="ok").first()


def patrones_por_proposicion(run):
    """{prop_id: {burbuja: patron}} sólo con patrones con suficientes opiniones."""
    out = defaultdict(dict)
    for p in run.patrones.select_related("burbuja", "proposicion__historia").order_by("burbuja__numero"):
        if p.opinan >= MIN_OPINAN_PATRON:
            out[p.proposicion_id][p.burbuja] = p
    return out


def consenso_y_division(run, n=10):
    """Proposiciones donde todas las burbujas coinciden, y donde más difieren."""
    por_prop = patrones_por_proposicion(run)
    une, divide = [], []
    for pid, pats in por_prop.items():
        if len(pats) < max(2, run.k):
            continue
        pcts = [p.pct_acuerdo for p in pats.values()]
        prop = next(iter(pats.values())).proposicion
        if min(pcts) >= UMBRAL_CONSENSO:
            une.append((prop, pats, min(pcts), True))
        elif max(pcts) <= 100 - UMBRAL_CONSENSO:
            une.append((prop, pats, 100 - max(pcts), False))
        divide.append((prop, pats, max(pcts) - min(pcts)))
    une.sort(key=lambda t: -t[2])
    divide.sort(key=lambda t: -t[2])
    return une[:n], [d for d in divide if d[2] >= 30][:n]


def distintivas(run, burbuja, n=3):
    """Proposiciones donde esta burbuja más se separa del resto."""
    por_prop = patrones_por_proposicion(run)
    out = []
    for pid, pats in por_prop.items():
        if burbuja not in pats:
            continue
        propio = pats[burbuja].pct_acuerdo
        otros = [p for b, p in pats.items() if b != burbuja]
        a = sum(p.acuerdo for p in otros)
        d = sum(p.desacuerdo for p in otros)
        if a + d == 0:
            continue
        resto = 100 * a / (a + d)
        out.append((pats[burbuja].proposicion, propio, resto, propio - resto))
    out.sort(key=lambda t: -abs(t[3]))
    return out[:n]


def burbuja_de(voter, run=None):
    run = run or ultimo_run()
    if not run:
        return None
    filtro = {"usuario": voter["usuario"]} if voter.get("usuario") else {"session_key": voter["session_key"]}
    m = BurbujaMiembro.objects.filter(run=run, **filtro).select_related("burbuja").first()
    return m.burbuja if m else None


def nombrar_burbujas(run):
    from core import parse

    for b in run.burbujas.all():
        dist = distintivas(run, b, n=7)
        if not dist:
            continue
        top = [
            {
                "titulo": prop.texto,
                "majority_opinion": "de acuerdo" if propio >= 50 else "en desacuerdo",
                "consensus": max(propio, 100 - propio) / 100,
            }
            for prop, propio, _resto, _d in dist
        ]
        desc = parse.generate_cluster_description(
            top_noticias=top,
            entities_positive=[],
            entities_negative=[],
            cluster_size=b.tamano,
            consensus_score=sum(t["consensus"] for t in top) / len(top),
        )
        if desc:
            b.nombre = desc.nombre[:80]
            b.descripcion = desc.descripcion[:300]
            b.save(update_fields=["nombre", "descripcion"])
