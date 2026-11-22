import pytest


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """Sin Redis el cache es una tabla en la base: crearla en la base de tests."""
    from django.conf import settings
    from django.core.management import call_command

    if settings.CACHES["default"]["BACKEND"].endswith("DatabaseCache"):
        with django_db_blocker.unblock():
            call_command("createcachetable", verbosity=0)


@pytest.fixture(autouse=True)
def _cache_limpio():
    """Cada test arranca con el cache vacío (locks, ratelimit, cache_page)."""
    from django.core.cache import cache

    try:
        cache.clear()
    except Exception:
        pass  # tests sin acceso a la base
    yield
