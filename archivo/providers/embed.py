"""
Embeddings para agrupar notas en historias.

- WorkersAIEmbedder: Cloudflare Workers AI (bge-m3, multilingüe).
- LiteLLMEmbedder: cualquier modelo de embeddings vía LiteLLM.
- FakeEmbedder: bolsa de palabras hasheada (determinístico, para tests).

Env: EMBEDDER=workers_ai|litellm|fake
"""

from __future__ import annotations

import hashlib
import math
import os
import re

import requests


def normalizar(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def coseno(a, b):
    if not a or not b:
        return 0.0
    return sum(x * y for x, y in zip(a, b))


class Embedder:
    nombre = "base"

    def embed(self, textos: list[str]) -> list[list[float]]:
        raise NotImplementedError


class WorkersAIEmbedder(Embedder):
    nombre = "workers_ai"

    def __init__(self):
        self.account_id = os.environ["CLOUDFLARE_ACCOUNT_ID"]
        self.token = os.environ["CLOUDFLARE_API_TOKEN"]
        self.modelo = os.environ.get("WORKERS_AI_EMBED_MODEL", "@cf/baai/bge-m3")

    def embed(self, textos):
        url = (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{self.account_id}/ai/run/{self.modelo}"
        )
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {self.token}"},
            json={"text": textos},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()["result"]["data"]
        return [normalizar(v) for v in data]


class LiteLLMEmbedder(Embedder):
    nombre = "litellm"

    def __init__(self):
        self.modelo = os.environ.get("LITELLM_EMBED_MODEL", "gemini/text-embedding-004")

    def embed(self, textos):
        from litellm import embedding

        resp = embedding(model=self.modelo, input=textos)
        return [normalizar(d["embedding"]) for d in resp.data]


class FakeEmbedder(Embedder):
    nombre = "fake"
    DIM = 256

    def embed(self, textos):
        out = []
        for t in textos:
            v = [0.0] * self.DIM
            for w in re.findall(r"\w{4,}", t.lower()):
                h = int(hashlib.md5(w.encode()).hexdigest(), 16)
                v[h % self.DIM] += 1.0
            out.append(normalizar(v))
        return out


_override = None


def set_embedder(embedder):
    global _override
    _override = embedder


def get_embedder(nombre: str | None = None) -> Embedder:
    if _override is not None and nombre is None:
        return _override
    nombre = nombre or os.environ.get("EMBEDDER", "workers_ai")
    return {
        "workers_ai": WorkersAIEmbedder,
        "litellm": LiteLLMEmbedder,
        "fake": FakeEmbedder,
    }[nombre]()
