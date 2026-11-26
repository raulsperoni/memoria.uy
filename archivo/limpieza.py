"""Texto repetido de cada medio: avisos de suscripción, muros de pago,
titulares de otras notas. Se reconoce porque la misma línea aparece en notas
de historias distintas del mismo medio.

Las líneas detectadas quedan en Medio.lineas_repetidas: una vez que el texto
guardado está limpio, la línea ya no se repite en él y no se podría volver a
detectar.
"""

from collections import defaultdict

from .models import Fuente

MUESTRA = 40  # notas recientes del medio que se miran
MIN_HISTORIAS = 3  # en cuántas historias distintas tiene que aparecer la línea
MIN_NOTAS = 5  # o en cuántas notas (si el aviso ya pegó notas en una sola historia)
MIN_LARGO = 20  # líneas más cortas («Compartir», «¡Hola») no cuentan solas


def _norm(linea: str) -> str:
    return " ".join(linea.split())


def detectar(medio, texto_nuevo: str = "") -> list[str]:
    """Líneas que se repiten en notas de historias distintas del medio,
    contando el texto que se está por guardar."""
    grupos, notas = defaultdict(set), defaultdict(int)
    recientes = (
        Fuente.objects.filter(medio=medio)
        .exclude(texto="")
        .order_by("-pk")
        .values_list("pk", "historia_id", "texto")[:MUESTRA]
    )
    muestras = [(f"h{h}" if h else f"f{pk}", t) for pk, h, t in recientes]
    if texto_nuevo:
        muestras.append(("nuevo", texto_nuevo))
    for grupo, texto in muestras:
        for linea in {_norm(x) for x in texto.split("\n")}:
            if len(linea) >= MIN_LARGO:
                grupos[linea].add(grupo)
                notas[linea] += 1
    return sorted(x for x, g in grupos.items() if len(g) >= MIN_HISTORIAS or notas[x] >= MIN_NOTAS)


def lineas_del_medio(medio, texto_nuevo: str = "") -> set[str]:
    """Las líneas conocidas del medio más las que se detecten ahora (que
    quedan guardadas)."""
    conocidas = set(medio.lineas_repetidas or [])
    nuevas = set(detectar(medio, texto_nuevo)) - conocidas
    if nuevas:
        medio.lineas_repetidas = sorted(conocidas | nuevas)
        medio.save(update_fields=["lineas_repetidas"])
    return conocidas | nuevas


def limpiar(texto: str, lineas: set[str]) -> str:
    if not texto or not lineas:
        return texto
    return "\n".join(x for x in texto.split("\n") if _norm(x) not in lineas).strip()
