"""Métricas de ingesta para el resumen diario de staff."""

from datetime import timedelta
from html import escape

from django.db.models import Count, Q, Sum
from django.utils import timezone

from .models import Cambio, Fuente, Historia, Medio, UsoProveedor

# Costos aproximados por operación (USD), para estimar el gasto diario.
COSTO_ESTIMADO = {
    ("cloudflare", "extraer"): 0.09 / 3600 * 2,  # ~2 s de browser
    ("cloudflare", "recrawl"): 0.09 / 3600 * 2,
    ("llm", "historia"): 0.0015,
    ("embed", "embed"): 0.00001,
}


def resumen_ingesta(horas=24):
    desde = timezone.now() - timedelta(hours=horas)
    hoy = timezone.localdate()
    fuentes = Fuente.objects.filter(descubierta_en__gte=desde)
    por_estado = dict(fuentes.values_list("estado").annotate(n=Count("id")))
    por_medio = (
        Medio.objects.filter(activo=True)
        .annotate(
            nuevas=Count("fuentes", filter=Q(fuentes__descubierta_en__gte=desde)),
            extraidas=Count(
                "fuentes",
                filter=Q(fuentes__descubierta_en__gte=desde, fuentes__estado__in=["extraida", "procesada"]),
            ),
        )
        .order_by("nombre")
    )
    uso = UsoProveedor.objects.filter(fecha__gte=hoy - timedelta(days=1))
    costo = 0.0
    for u in uso:
        costo += u.costo_usd or u.cantidad * COSTO_ESTIMADO.get((u.proveedor, u.operacion), 0)
    return {
        "descubiertas": fuentes.count(),
        "por_estado": por_estado,
        "medios": [(m.nombre, m.nuevas, m.extraidas) for m in por_medio],
        "medios_caidos": [m.nombre for m in por_medio if m.nuevas == 0],
        "historias": Historia.objects.filter(procesada_en__gte=desde).count(),
        "cambios": Cambio.objects.filter(detectado_en__gte=desde).count(),
        "cambios_sentido": Cambio.objects.filter(detectado_en__gte=desde, cambia_sentido__gte=0.5).count(),
        "errores": por_estado.get("error", 0),
        "costo_usd": round(costo, 3),
    }


def lineas_texto(r):
    out = [
        "",
        "ARCHIVO (últimas 24 h)",
        f"  Notas descubiertas: {r['descubiertas']}  {r['por_estado']}",
        f"  Historias procesadas: {r['historias']}",
        f"  Cambios detectados: {r['cambios']} ({r['cambios_sentido']} cambian el sentido)",
        f"  Costo estimado: US$ {r['costo_usd']}",
    ]
    if r["medios_caidos"]:
        out.append(f"  ⚠ Medios sin notas nuevas: {', '.join(r['medios_caidos'])}")
    out.append("  Por medio (nuevas / extraídas):")
    out += [f"    {n}: {a} / {b}" for n, a, b in r["medios"]]
    return out


def lineas_html(r):
    out = [
        "<h3>🗄️ Archivo (últimas 24 h)</h3><ul>",
        f"<li>Notas descubiertas: {r['descubiertas']} {escape(str(r['por_estado']))}</li>",
        f"<li>Historias procesadas: {r['historias']}</li>",
        f"<li>Cambios detectados: {r['cambios']} ({r['cambios_sentido']} cambian el sentido)</li>",
        f"<li>Costo estimado: US$ {r['costo_usd']}</li></ul>",
    ]
    if r["medios_caidos"]:
        out.append(f"<p>⚠️ Medios sin notas nuevas: {escape(', '.join(r['medios_caidos']))}</p>")
    out.append("<table border='1' cellpadding='4'><tr><th>Medio</th><th>Nuevas</th><th>Extraídas</th></tr>")
    out += [f"<tr><td>{escape(n)}</td><td>{a}</td><td>{b}</td></tr>" for n, a, b in r["medios"]]
    out.append("</table>")
    return out
