"""
Clustering estilo Polis, usado por juego/burbujas.py para agrupar a quienes
votan las frases del juego de forma parecida.
"""

from .hierarchical import group_clusters
from .metrics import compute_silhouette_score
from .pca import compute_sparsity_aware_pca

__all__ = ["compute_sparsity_aware_pca", "group_clusters", "compute_silhouette_score"]
