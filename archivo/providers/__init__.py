"""
Proveedores intercambiables (extracción, decisiones, embeddings, storage).

Cada uno se elige por variable de entorno; en tests se usan los "fake".
"""

from .extract import get_extractor  # noqa: F401
from .decide import get_decider  # noqa: F401
from .embed import get_embedder  # noqa: F401
from .storage import get_storage  # noqa: F401
from .wikidata import get_enriquecedor  # noqa: F401
