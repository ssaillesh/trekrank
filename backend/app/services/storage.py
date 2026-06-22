"""Object storage abstraction. Defaults to local filesystem (free, no Docker/MinIO).

Set STORAGE_BACKEND=s3 to switch to MinIO/S3 (boto3 path left as an extension point).
Returns public URLs served by the API's /media static mount.
"""
import os
import uuid

from app.config import settings


def _local_dir() -> str:
    os.makedirs(settings.local_storage_dir, exist_ok=True)
    return settings.local_storage_dir


def save_bytes(data: bytes, *, ext: str = "jpg", subdir: str = "photos") -> str:
    """Persist bytes and return a public URL."""
    name = f"{uuid.uuid4().hex}.{ext.lstrip('.')}"
    if settings.storage_backend == "local":
        d = os.path.join(_local_dir(), subdir)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, name)
        with open(path, "wb") as f:
            f.write(data)
        return f"{settings.public_base_url}/media/{subdir}/{name}"
    raise NotImplementedError("S3 backend not enabled in MVP; use STORAGE_BACKEND=local")


def read_bytes_from_url(url: str) -> bytes | None:
    """Read back a previously-saved local file given its public URL."""
    if settings.storage_backend != "local":
        return None
    prefix = f"{settings.public_base_url}/media/"
    if not url.startswith(prefix):
        return None
    rel = url[len(prefix):]
    path = os.path.join(settings.local_storage_dir, rel)
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return f.read()
