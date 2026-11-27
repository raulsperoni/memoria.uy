"""
Corre las tareas periódicas que estén "vencidas" y termina.

Reemplaza a Celery beat + worker + Redis: en Railway se ejecuta como cron
service cada 15 min (`python manage.py tick`). El estado (última corrida de
cada tarea) se guarda en `TareaCorrida`, no en el cache: el cache de base
borra entradas al pasar `MAX_ENTRIES` y eso hacía repetir las tareas diarias
(registro 0018). Cada tarea mantiene su propio `task_lock`, así que dos ticks superpuestos no duplican
trabajo.

    manage.py tick              # corre lo vencido
    manage.py tick --forzar X   # corre la tarea X ya
    manage.py tick --listar     # muestra el estado
"""

import logging
import os
import time
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


def _medios():
    """Carga los medios iniciales si no hay y detecta feeds de los que no tengan."""
    from django.core.management import call_command

    from archivo.models import Medio

    if not Medio.objects.exists():
        call_command("cargar_medios")
    sin_feeds = Medio.objects.filter(activo=True, rss_urls=[], sitemap_urls=[]).count()
    if sin_feeds:
        call_command("detectar_feeds")
    return f"medios={Medio.objects.count()} sin_feeds_antes={sin_feeds}"


def _ciclo_ingesta():
    from archivo.tasks import ciclo_ingesta

    return ciclo_ingesta()


def _procesar_historias():
    from archivo.tasks import procesar_historias

    return procesar_historias()


def _recrawls():
    from archivo.tasks import recrawls_pendientes

    return recrawls_pendientes()


def _tonos():
    from archivo.tasks import tonos_pendientes

    return tonos_pendientes()


def _fichas():
    from archivo.tasks import fichas_pendientes

    return fichas_pendientes()


def _cerrar():
    from archivo.tasks import cerrar_historias

    return cerrar_historias()


def _jornada():
    from juego.tasks import armar_jornada_del_dia

    return armar_jornada_del_dia()


def _burbujas():
    from juego.tasks import calcular_burbujas_diario

    return calcular_burbujas_diario()


def _resumen_staff():
    from core.tasks import send_daily_staff_summary

    return send_daily_staff_summary()


# nombre: (función, cada (timedelta) | None, a partir de "HH:MM" local | None)
# - con `cada`: corre si pasó ese tiempo desde la última vez
# - con hora: corre una vez por día, la primera vez que el tick pasa después de esa hora
TAREAS = {
    "medios": (_medios, timedelta(hours=23), None),
    "procesar_historias": (_procesar_historias, timedelta(minutes=14), None),
    "ciclo_ingesta": (_ciclo_ingesta, timedelta(minutes=29), None),
    "recrawls": (_recrawls, timedelta(minutes=59), None),
    "tonos": (_tonos, timedelta(minutes=29), None),
    "cerrar_historias": (_cerrar, timedelta(minutes=59), None),
    "fichas": (_fichas, timedelta(minutes=59), None),
    "burbujas": (_burbujas, None, "02:15"),
    "jornada": (_jornada, None, "05:30"),
    "resumen_staff": (_resumen_staff, None, os.environ.get("DAILY_SUMMARY_HORA", "09:00")),
}
# Orden de ejecución: primero lo que alimenta a lo siguiente.
# Tonos y fichas van al final: son lentas y no alimentan a ninguna otra.
ORDEN = ["medios", "ciclo_ingesta", "procesar_historias", "recrawls", "cerrar_historias", "burbujas", "jornada", "resumen_staff", "tonos", "fichas"]

def ultima(nombre):
    from core.models import TareaCorrida

    return TareaCorrida.objects.filter(nombre=nombre).values_list("ultima", flat=True).first()


def marcar(nombre, cuando=None):
    from core.models import TareaCorrida

    TareaCorrida.objects.update_or_create(nombre=nombre, defaults={"ultima": cuando or timezone.now()})


def vencida(nombre, ahora=None):
    _, cada, hora = TAREAS[nombre]
    ahora = ahora or timezone.now()
    previa = ultima(nombre)
    if cada is not None:
        return previa is None or ahora - previa >= cada
    hh, mm = map(int, hora.split(":"))
    local = timezone.localtime(ahora)
    umbral = local.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if local < umbral:
        return False
    return previa is None or timezone.localtime(previa) < umbral


def correr(nombre):
    fn = TAREAS[nombre][0]
    t = time.monotonic()
    try:
        res = fn()
        estado = "ok"
    except Exception as e:  # una tarea rota no frena a las demás
        logger.exception("Tarea %s falló", nombre)
        res, estado = str(e)[:200], "error"
    marcar(nombre)
    return estado, res, time.monotonic() - t


class Command(BaseCommand):
    help = "Corre las tareas periódicas vencidas (reemplazo de Celery beat)."

    def add_arguments(self, parser):
        parser.add_argument("--forzar", choices=sorted(TAREAS), action="append", default=[])
        parser.add_argument("--listar", action="store_true")

    def handle(self, *args, forzar, listar, **opts):
        if listar:
            for n in ORDEN:
                u = ultima(n)
                self.stdout.write(f"{n:20s} última: {timezone.localtime(u):%d/%m %H:%M}" if u else f"{n:20s} nunca")
            return
        a_correr = forzar or [n for n in ORDEN if vencida(n)]
        if not a_correr:
            self.stdout.write("nada vencido")
        for n in a_correr:
            estado, res, seg = correr(n)
            self.stdout.write(f"[{estado}] {n} ({seg:.1f}s): {res}")
