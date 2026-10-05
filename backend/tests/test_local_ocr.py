"""Local Tesseract OCR feature tests (iteration 3)."""
import os
import time
import pytest
import requests

SCANNED_DOC_ID = open("/app/tests/fixtures/scanned_docid").read().strip()
EXPECTED_P2_PREFIX = "الحمد لله رب العالمين والصلاة والسلام على نبينا محمد"


# ---------- static code checks ----------

class TestNoPaidAIForOCR:
    def test_ocr_module_has_no_gemini(self):
        src = open("/app/backend/ocr.py").read()
        for forbidden in ("gemini", "Gemini", "google.generativeai", "openai", "anthropic"):
            assert forbidden not in src, f"ocr.py should not reference {forbidden}"

    def test_backend_has_no_llm_ocr_calls(self):
        # server.py may still have the manual OCR route; just make sure OCR is routed
        # through local ocr.py (وليس عبر مزودات ذكاء اصطناعي خارجية)
        src = open("/app/backend/server.py").read()
        assert "http://" not in src and "https://" not in src
        assert "google.generativeai" not in src
        # must call into local ocr module
        assert "from ocr import" in src or "import ocr" in src


# ---------- pre-processed scanned document ----------

class TestPreProcessedScannedDoc:
    def test_doc_ready(self, admin_session, base_url):
        r = admin_session.get(f"{base_url}/api/documents/{SCANNED_DOC_ID}", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["page_count"] == 10
        assert d["status"] in ("ready", "ready_with_warnings")
        assert d["extractor_version"] >= 3

    def test_ocr_engine_tag_on_pages(self, admin_session, base_url):
        r = admin_session.get(f"{base_url}/api/documents/{SCANNED_DOC_ID}/pages", timeout=30)
        assert r.status_code == 200
        pages = r.json()
        ocr_pages = [p for p in pages if p["status"] == "ocr_done"]
        assert len(ocr_pages) >= 5
        for p in ocr_pages:
            engine = p.get("ocr_engine", "")
            assert "tesseract" in engine.lower(), f"expected tesseract engine on p{p['page_number']}, got {engine!r}"
            assert "ara" in engine.lower() or "arabic" in engine.lower()
            # confidence sensible
            conf = p.get("ocr_confidence")
            if conf is not None:
                assert 0.0 <= conf <= 1.0

    def test_content_order_and_p2(self, admin_session, base_url):
        r = admin_session.get(f"{base_url}/api/documents/{SCANNED_DOC_ID}/content", timeout=30)
        assert r.status_code == 200
        data = r.json()
        # content endpoint typically returns per-page content
        if isinstance(data, dict) and "pages" in data:
            pages = data["pages"]
        else:
            pages = data
        # find page_number 2
        p2 = None
        for p in pages:
            if (p.get("page_number") == 2) or (p.get("page") == 2):
                p2 = p
                break
        assert p2 is not None, "page 2 not found in /content"
        # content shape: pages[].lines[].w[] (words)
        text = p2.get("text") or p2.get("content") or ""
        if not text:
            words = []
            for ln in p2.get("lines", []):
                words.extend(ln.get("w", []))
            text = " ".join(words)
        head = text[:120]
        # OCR may not be character-perfect — expect first few words of the opening line
        for w in ("الحمد", "لله", "العالمين"):
            assert w in head, f"missing {w!r} in p2 opening: {head!r}"
        # verify logical order: 'الحمد' comes before 'العالمين'
        assert text.index("الحمد") < text.index("العالمين")


# ---------- upload the user's scanned 10p PDF fresh ----------

class TestUploadScannedPipeline:
    def test_upload_scanned_pdf_auto_ocr(self, admin_session, base_url):
        with open("/app/tests/fixtures/scanned_tamour_10p.pdf", "rb") as fh:
            files = {"file": ("TEST_scanned_tamour.pdf", fh, "application/pdf")}
            r = admin_session.post(f"{base_url}/api/documents", files=files, timeout=120)
        if r.status_code == 503:
            pytest.skip(f"storage transiently 503: {r.text}")
        assert r.status_code == 200, r.text
        doc_id = r.json()["document_id"]
        try:
            # poll up to 90s
            deadline = time.time() + 90
            stages_seen = set()
            final = None
            while time.time() < deadline:
                g = admin_session.get(f"{base_url}/api/documents/{doc_id}", timeout=30)
                assert g.status_code == 200
                d = g.json()
                stage = d.get("stage") or d.get("processing_stage")
                if stage:
                    stages_seen.add(stage)
                if d["status"] != "processing":
                    final = d
                    break
                time.sleep(1.5)
            assert final is not None, "doc never finished"
            assert final["status"] in ("ready", "ready_with_warnings"), f"final={final['status']}"
            assert final["page_count"] == 10

            pr = admin_session.get(f"{base_url}/api/documents/{doc_id}/pages", timeout=30)
            pages = pr.json()
            statuses = [p["status"] for p in pages]
            # at least a few pages should be auto OCR'd (not left as needs_ocr)
            ocr_done = [p for p in pages if p["status"] == "ocr_done"]
            needs_ocr = [p for p in pages if p["status"] == "needs_ocr"]
            assert len(ocr_done) >= 3, f"auto-ocr too few: {statuses}"
            # verify engine tag + conf
            sample = ocr_done[0]
            assert "tesseract" in (sample.get("ocr_engine") or "").lower()
            if sample.get("ocr_confidence") is not None:
                assert 0.0 <= sample["ocr_confidence"] <= 1.0
            # no needs_ocr remain (auto OCR handled all)
            assert len(needs_ocr) == 0, f"needs_ocr still has {len(needs_ocr)} pages after auto-ocr"
        finally:
            admin_session.delete(f"{base_url}/api/documents/{doc_id}", timeout=30)


# ---------- manual OCR POST route ----------

class TestManualOCR:
    """Manual OCR button: POST /api/documents/{id}/ocr with pages=[n]."""

    def test_manual_ocr_on_scanned_doc_already_ocr(self, admin_session, base_url):
        # pick an existing ocr_done page; manual OCR should still succeed (re-OCR)
        pr = admin_session.get(f"{base_url}/api/documents/{SCANNED_DOC_ID}/pages", timeout=30)
        pages = pr.json()
        target = next((p for p in pages if p["status"] in ("ocr_done", "warning", "empty", "needs_ocr", "ocr_failed")), None)
        assert target is not None
        pn = target["page_number"]
        r = admin_session.post(
            f"{base_url}/api/documents/{SCANNED_DOC_ID}/ocr",
            json={"pages": [pn]}, timeout=60,
        )
        # route may return 200/202 or 409 if pending job
        assert r.status_code in (200, 202, 409), f"manual ocr: {r.status_code} {r.text}"
        if r.status_code == 409:
            pytest.skip("job already running for this doc")
        # wait up to 30s for processing to complete
        deadline = time.time() + 30
        while time.time() < deadline:
            g = admin_session.get(f"{base_url}/api/documents/{SCANNED_DOC_ID}", timeout=30)
            if g.json()["status"] != "processing":
                break
            time.sleep(1)
        # verify engine tag now present on that page
        pr2 = admin_session.get(f"{base_url}/api/documents/{SCANNED_DOC_ID}/pages/{pn}", timeout=30)
        if pr2.status_code == 200:
            page = pr2.json()
            if page.get("status") == "ocr_done":
                assert "tesseract" in (page.get("ocr_engine") or "").lower()
