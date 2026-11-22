from django.apps import AppConfig


class JuegoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "juego"
    verbose_name = "Juego diario"

    def ready(self):
        from . import signals  # noqa: F401
