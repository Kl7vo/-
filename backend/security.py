from types import SimpleNamespace

from fastapi import HTTPException

try:
    import magic
except ImportError:  # PyMuPDF structural validation remains the required fallback
    magic = None


def validate_pdf_content(file_content: bytes):
    """Reject a file whose MIME signature is not PDF when libmagic is available."""
    if magic is not None and magic.from_buffer(file_content, mime=True) != "application/pdf":
        raise HTTPException(status_code=422, detail="Invalid PDF format: fake extension detected")


def apply_security_headers(response, request):
    """Apply response headers without assuming a particular ASGI app or framework."""
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'")
    scheme = getattr(getattr(request, "url", SimpleNamespace(scheme="")), "scheme", "")
    forwarded = request.headers.get("x-forwarded-proto", "")
    if scheme == "https" or forwarded == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response
