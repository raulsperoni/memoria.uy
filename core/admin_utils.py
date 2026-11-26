"""Piezas comunes de los ModelAdmin: insignias de color y links entre objetos."""

from django.urls import reverse
from django.utils.html import format_html


def badge(texto, tono="mute"):
    """tono: ok / warn / err / info / mute (clases en core/admin/memoria.css)."""
    return format_html('<span class="mu-badge mu-{}">{}</span>', tono, texto)


def link_admin(obj, texto=None):
    """Link a la pantalla de cambio de otro objeto en el admin."""
    if obj is None:
        return "—"
    url = reverse(f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change", args=[obj.pk])
    return format_html('<a href="{}">{}</a>', url, texto if texto is not None else str(obj))


def pct(valor, tono_alto="ok", umbral=0.5):
    """Probabilidades 0..1 de Jev como porcentaje coloreado (alto = bien)."""
    if valor is None:
        return badge("—")
    tono = tono_alto if valor >= umbral else "err"
    return badge(f"{valor:.0%}", tono)
