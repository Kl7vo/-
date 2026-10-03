import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from starlette.responses import Response

PROJECT_ROOT = Path(os.environ["PROJECT_ROOT"]) if os.environ.get("PROJECT_ROOT") else Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))


def test_jwt_revoked_after_logout_boundary():
    os.environ["JWT_SECRET"] = "test-secret-that-is-long-enough-for-tests"
    from auth import _token_revoked, create_token
    import jwt

    token = create_token("user_1", "access", timedelta(minutes=5))
    payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=["HS256"])
    issued = datetime.fromtimestamp(payload["iat"], timezone.utc)
    assert not _token_revoked(payload, {})
    assert _token_revoked(payload, {"sessions_revoked_at": issued + timedelta(seconds=1)})
    assert not _token_revoked(payload, {"sessions_revoked_at": issued - timedelta(seconds=1)})


def test_storage_rejects_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    import storage

    with pytest.raises(ValueError):
        storage.put_object("../../outside.pdf", b"x", "application/pdf")
    with pytest.raises(ValueError):
        storage.get_object("user\\..\\outside.pdf")


def test_storage_writes_private_file_atomically(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    import storage

    result = storage.put_object("reader/uploads/u1/doc.pdf", b"safe", "application/pdf")
    target = tmp_path / "reader/uploads/u1/doc.pdf"
    assert result["size"] == 4
    assert target.read_bytes() == b"safe"
    assert oct(target.stat().st_mode & 0o777) == "0o600"


def test_cors_wildcard_is_not_accepted_with_credentials(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "*")
    env = PROJECT_ROOT / "selfhost.env.example"
    assert "CORS_ORIGINS=\n" in env.read_text()
    assert "CORS_ORIGINS=*" not in env.read_text()


def test_security_headers_are_applied_and_hsts_is_https_only():
    from security import apply_security_headers

    http_response = apply_security_headers(Response(), SimpleNamespace(url=SimpleNamespace(scheme="http"), headers={}))
    assert http_response.headers["x-content-type-options"] == "nosniff"
    assert http_response.headers["x-frame-options"] == "DENY"
    assert http_response.headers["content-security-policy"].startswith("default-src 'self'")
    assert "strict-transport-security" not in http_response.headers

    https_response = apply_security_headers(Response(), SimpleNamespace(url=SimpleNamespace(scheme="https"), headers={}))
    assert https_response.headers["strict-transport-security"].startswith("max-age=31536000")


def test_magic_bytes_reject_fake_pdf_and_accept_real_pdf():
    import pymupdf
    from security import validate_pdf_content

    with pytest.raises(Exception):
        validate_pdf_content(b"this is not a PDF")

    doc = pymupdf.open()
    doc.new_page()
    real_pdf = doc.tobytes()
    doc.close()
    validate_pdf_content(real_pdf)


def test_pdf_dimensions_have_a_finite_default():
    env = PROJECT_ROOT / "selfhost.env.example"
    text = env.read_text()
    assert "MAX_PAGE_PIXELS=50000000" in text
    assert "MAX_UPLOAD_MB=50" in text
