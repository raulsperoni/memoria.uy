"""
Almacenamiento privado de snapshots (HTML gzip, clave = sha256 del contenido).

- LocalStorage: disco (desarrollo). Env: SNAPSHOT_DIR (default MEDIA_ROOT/snapshots).
- R2Storage: Cloudflare R2 vía API S3. Env: R2_ACCOUNT_ID (o CLOUDFLARE_ACCOUNT_ID),
  R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET.

Env: SNAPSHOT_STORAGE=local|r2
"""

from __future__ import annotations

import gzip
import hashlib
import os
from pathlib import Path


def clave_para(contenido: bytes) -> str:
    h = hashlib.sha256(contenido).hexdigest()
    return f"snapshots/{h[:2]}/{h}.html.gz"


class Storage:
    def put(self, contenido: bytes) -> str:
        raise NotImplementedError

    def get(self, clave: str) -> bytes:
        raise NotImplementedError


class LocalStorage(Storage):
    def __init__(self, base=None):
        if base is None:
            from django.conf import settings

            base = os.environ.get(
                "SNAPSHOT_DIR", os.path.join(settings.MEDIA_ROOT, "private")
            )
        self.base = Path(base)

    def put(self, contenido):
        clave = clave_para(contenido)
        ruta = self.base / clave
        if not ruta.exists():
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_bytes(gzip.compress(contenido))
        return clave

    def get(self, clave):
        return gzip.decompress((self.base / clave).read_bytes())


class R2Storage(Storage):
    def __init__(self):
        import boto3

        account = os.environ.get("R2_ACCOUNT_ID") or os.environ["CLOUDFLARE_ACCOUNT_ID"]
        self.bucket = os.environ.get("R2_BUCKET", "memoria-snapshots")
        self.s3 = boto3.client(
            "s3",
            endpoint_url=f"https://{account}.r2.cloudflarestorage.com",
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
        )

    def put(self, contenido):
        clave = clave_para(contenido)
        self.s3.put_object(
            Bucket=self.bucket,
            Key=clave,
            Body=gzip.compress(contenido),
            ContentType="text/html",
            ContentEncoding="gzip",
        )
        return clave

    def get(self, clave):
        obj = self.s3.get_object(Bucket=self.bucket, Key=clave)
        return gzip.decompress(obj["Body"].read())


def get_storage() -> Storage:
    if os.environ.get("SNAPSHOT_STORAGE", "local") == "r2":
        return R2Storage()
    return LocalStorage()
