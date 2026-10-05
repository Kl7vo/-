import os
import re
import tempfile
from pathlib import Path

APP_NAME = "arabic-rsvp-reader"
CACHE_DIR = Path(os.environ.get("PDF_CACHE_DIR", "/tmp/pdfcache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
try:
    CACHE_DIR.chmod(0o700)
except OSError:
    pass

_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9._/-]+$")


def _validate_object_path(path: str) -> str:
    if not isinstance(path, str) or not path or len(path) > 512 or "\\" in path:
        raise ValueError("invalid storage path")
    parts = Path(path).parts
    if any(part in ("", ".", "..") for part in parts) or not _SAFE_COMPONENT.fullmatch(path):
        raise ValueError("invalid storage path")
    return path


def _local_dir() -> Path:
    value = os.environ.get("STORAGE_DIR")
    if not value:
        raise RuntimeError("STORAGE_DIR must be configured for local storage")
    return Path(value).expanduser().resolve()


def _local_target(path: str) -> Path:
    root = _local_dir()
    target = (root / _validate_object_path(path)).resolve()
    if target != root and root not in target.parents:
        raise ValueError("invalid storage path")
    return target


def _atomic_write(target: Path, data: bytes):
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(prefix=".upload-", dir=str(target.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def put_object(path: str, data: bytes, content_type: str) -> dict:
    path = _validate_object_path(path)
    _atomic_write(_local_target(path), data)
    return {"path": path, "size": len(data)}


def get_object(path: str) -> bytes:
    return _local_target(_validate_object_path(path)).read_bytes()


def _cache_path(document_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{32}", document_id or ""):
        raise ValueError("invalid document id")
    return CACHE_DIR / f"{document_id}.pdf"


def get_pdf_bytes(document_id: str, storage_path: str) -> bytes:
    cached = _cache_path(document_id)
    if cached.exists():
        return cached.read_bytes()
    data = get_object(storage_path)
    _atomic_write(cached, data)
    return data


def cache_pdf(document_id: str, data: bytes):
    _atomic_write(_cache_path(document_id), data)


def drop_cache(document_id: str):
    _cache_path(document_id).unlink(missing_ok=True)
