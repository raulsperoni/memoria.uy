"""Lee docs/decisiones/ para la línea de tiempo de «Acerca de»."""

import re
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

from django.conf import settings

REPO = "https://github.com/raulsperoni/memoria.uy"
CARPETA = Path(settings.BASE_DIR) / "docs" / "decisiones"
ARCHIVO = re.compile(r"^(\d{4})-[\w-]+\.md$")
TITULO = re.compile(r"^#\s+\d{4}\s+—\s+(.+)$", re.M)
CAMPOS = re.compile(r"^\*Fecha: (\d{4}-\d{2}-\d{2}) · Estado: ([^·]+?) · Commits: ([0-9a-f, ]+)\*$", re.M)


@dataclass
class Decision:
    numero: str
    titulo: str
    fecha: date
    estado: str
    commits: list = field(default_factory=list)
    resumen: str = ""
    archivo: str = ""

    @property
    def url(self):
        return f"{REPO}/blob/main/docs/decisiones/{self.archivo}"

    @property
    def vigente(self):
        return self.estado.startswith("vigente")

    def commit_urls(self):
        return [(c, f"{REPO}/commit/{c}") for c in self.commits]


def leer(path: Path) -> Decision:
    texto = path.read_text(encoding="utf-8")
    titulo, campos = TITULO.search(texto), CAMPOS.search(texto)
    if not titulo or not campos:
        raise ValueError(f"{path.name}: falta el título o la línea de Fecha/Estado/Commits")
    resumen = ""
    m = re.search(r"^## Decisión\s*\n+(.+?)(?:\n\n|\Z)", texto, re.M | re.S)
    if m:
        resumen = " ".join(m.group(1).split())
        resumen = re.sub(r"`([^`]+)`", r"\1", resumen)
    return Decision(
        numero=ARCHIVO.match(path.name).group(1),
        titulo=titulo.group(1).strip(),
        fecha=date.fromisoformat(campos.group(1)),
        estado=campos.group(2).strip(),
        commits=[c.strip() for c in campos.group(3).split(",") if c.strip()],
        resumen=resumen,
        archivo=path.name,
    )


@lru_cache(maxsize=1)
def todas() -> tuple:
    if not CARPETA.exists():
        return ()
    return tuple(leer(p) for p in sorted(CARPETA.iterdir()) if ARCHIVO.match(p.name))
