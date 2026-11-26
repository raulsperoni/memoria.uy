from django.contrib.staticfiles.storage import StaticFilesStorage
from whitenoise.storage import CompressedManifestStaticFilesStorage


class EstaticosConHash(CompressedManifestStaticFilesStorage):
    """Estáticos con el hash en el nombre (WhiteNoise los sirve con
    `Cache-Control: max-age=31536000, immutable`). Si falta el manifest (tests,
    antes de `collectstatic`) devuelve el nombre sin hash en vez de fallar."""

    manifest_strict = False

    def url(self, name, force=False):
        try:
            return super().url(name, force)
        except ValueError:  # el archivo no está en STATIC_ROOT (tests, dev sin collectstatic)
            return StaticFilesStorage.url(self, name)
