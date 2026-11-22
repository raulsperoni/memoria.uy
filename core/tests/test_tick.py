from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone

from core.management.commands import tick


def _local(h, m, dia=0):
    tz = timezone.get_current_timezone()
    base = timezone.localtime().replace(hour=h, minute=m, second=0, microsecond=0)
    return base + timedelta(days=dia)


@pytest.mark.django_db
def test_vencida_por_intervalo():
    ahora = timezone.now()
    assert tick.vencida("procesar_historias", ahora)
    cache.set(tick.CLAVE.format("procesar_historias"), ahora - timedelta(minutes=5), None)
    assert not tick.vencida("procesar_historias", ahora)
    cache.set(tick.CLAVE.format("procesar_historias"), ahora - timedelta(minutes=15), None)
    assert tick.vencida("procesar_historias", ahora)


@pytest.mark.django_db
def test_vencida_diaria():
    antes = _local(5, 0)
    despues = _local(5, 45)
    assert not tick.vencida("jornada", antes)
    assert tick.vencida("jornada", despues)
    cache.set(tick.CLAVE.format("jornada"), despues, None)
    assert not tick.vencida("jornada", despues + timedelta(minutes=30))
    assert tick.vencida("jornada", despues + timedelta(days=1))


@pytest.mark.django_db
def test_tick_corre_lo_vencido_y_aisla_errores():
    llamadas = []
    tareas = {
        "a": (lambda: llamadas.append("a") or "ok-a", timedelta(minutes=10), None),
        "b": (lambda: 1 / 0, timedelta(minutes=10), None),
        "c": (lambda: llamadas.append("c"), timedelta(minutes=10), None),
    }
    with patch.object(tick, "TAREAS", tareas), patch.object(tick, "ORDEN", ["a", "b", "c"]):
        tick.Command().handle(forzar=[], listar=False)
        assert llamadas == ["a", "c"]  # b falló pero c corrió igual
        tick.Command().handle(forzar=[], listar=False)
        assert llamadas == ["a", "c"]  # nada vencido en la segunda
        tick.Command().handle(forzar=["a"], listar=False)
        assert llamadas == ["a", "c", "a"]


@pytest.mark.django_db
def test_tarea_medios_carga_si_no_hay():
    from archivo.models import Medio

    with patch("django.core.management.call_command") as cc:
        tick._medios()
    nombres = [c.args[0] for c in cc.call_args_list]
    assert nombres == ["cargar_medios"]  # no hay medios reales en el mock → no detecta
    assert Medio.objects.count() == 0
