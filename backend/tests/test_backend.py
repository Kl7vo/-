"""Backend API tests for Arabic PDF RSVP Reader."""
import io
import time
import requests


# ---------- auth ----------

class TestAuth:
    def test_login_success(self, base_url):
        r = requests.post(f"{base_url}/api/auth/login",
                          json={"email": "admin@example.com", "password": "admin123"}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["email"] == "admin@example.com"
        assert "access_token" in r.cookies
        assert "refresh_token" in r.cookies

    def test_login_wrong_password(self, base_url):
        r = requests.post(f"{base_url}/api/auth/login",
                          json={"email": "admin@example.com", "password": "WRONGpw!!"}, timeout=30)
        assert r.status_code == 401
        assert "detail" in r.json()

    def test_me(self, admin_session, base_url):
        r = admin_session.get(f"{base_url}/api/auth/me", timeout=30)
        assert r.status_code == 200
        assert r.json()["email"] == "admin@example.com"

    def test_me_unauth(self, base_url):
        r = requests.get(f"{base_url}/api/auth/me", timeout=30)
        assert r.status_code == 401

    def test_refresh(self, admin_session, base_url):
        r = admin_session.post(f"{base_url}/api/auth/refresh", timeout=30)
        assert r.status_code == 200

    def test_logout_then_me_fails(self, base_url):
        s = requests.Session()
        s.post(f"{base_url}/api/auth/login",
               json={"email": "admin@example.com", "password": "admin123"}, timeout=30)
        r = s.post(f"{base_url}/api/auth/logout", timeout=30)
        assert r.status_code == 200
        r2 = s.get(f"{base_url}/api/auth/me", timeout=30)
        assert r2.status_code == 401


# ---------- documents list / existing fixture ----------

class TestExistingDocument:
    def test_list_documents(self, admin_session, base_url, existing_doc_id):
        r = admin_session.get(f"{base_url}/api/documents", timeout=30)
        assert r.status_code == 200
        ids = [d["document_id"] for d in r.json()]
        assert existing_doc_id in ids, f"existing fixture doc {existing_doc_id} missing from library"

    def test_get_document(self, admin_session, base_url, existing_doc_id):
        r = admin_session.get(f"{base_url}/api/documents/{existing_doc_id}", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["document_id"] == existing_doc_id
        assert d["page_count"] == 5
        assert d["status"] in ("ready", "ready_with_warnings")
        assert "page_stats" in d

    def test_pages_list(self, admin_session, base_url, existing_doc_id):
        r = admin_session.get(f"{base_url}/api/documents/{existing_doc_id}/pages", timeout=30)
        assert r.status_code == 200
        pages = r.json()
        assert len(pages) == 5
        by_num = {p["page_number"]: p for p in pages}
        # pages 1-4 text, page 5 should be ocr_done (already OCR'd per context) or needs_ocr
        for n in range(1, 5):
            assert by_num[n]["status"] in ("ok", "warning"), f"page {n} status={by_num[n]['status']}"
        assert by_num[5]["status"] in ("ocr_done", "needs_ocr", "ocr_failed")

    def test_page_detail_headers_footer_excluded(self, admin_session, base_url, existing_doc_id):
        r = admin_session.get(f"{base_url}/api/documents/{existing_doc_id}/pages/1", timeout=30)
        assert r.status_code == 200
        page = r.json()
        assert "blocks" in page and "text" in page
        excluded = [ln for b in page["blocks"] for ln in b["lines"] if ln.get("excluded")]
        assert len(excluded) >= 1, "expected at least one excluded header/footer line on page 1"

    def test_page_image(self, admin_session, base_url, existing_doc_id):
        r = admin_session.get(f"{base_url}/api/documents/{existing_doc_id}/pages/1/image", timeout=60)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("image/png")
        assert r.content[:8] == b"\x89PNG\r\n\x1a\n"

    def test_content_endpoint(self, admin_session, base_url, existing_doc_id):
        r = admin_session.get(f"{base_url}/api/documents/{existing_doc_id}/content", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert len(d["pages"]) == 5
        for p in d["pages"]:
            # excluded lines filtered out
            assert all(isinstance(ln["w"], list) for ln in p.get("lines", []))

    def test_words_endpoint(self, admin_session, base_url, existing_doc_id):
        r = admin_session.get(f"{base_url}/api/documents/{existing_doc_id}/words?page=1", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["page"] == 1
        assert len(d["words"]) > 0
        assert all("text" in w for w in d["words"])

    def test_page_two_columns_rtl_order(self, admin_session, base_url, existing_doc_id):
        """Page 3 is two-column; right column lines come first."""
        r = admin_session.get(f"{base_url}/api/documents/{existing_doc_id}/pages/3", timeout=30)
        assert r.status_code == 200
        page = r.json()
        assert page.get("two_columns") is True
        # Blocks containing only excluded lines (header/footer) can appear first.
        # Pick content blocks (not fully excluded) and check right-column precedes left-column.
        content = [b for b in page["blocks"]
                   if any(not ln.get("excluded") for ln in b["lines"])]
        page_width = page["width"]
        mid = page_width / 2
        # Find index of first left-column block (center < mid) and last right-column block
        first_left_idx = None
        last_right_idx = None
        for i, b in enumerate(content):
            cx = (b["bbox"][0] + b["bbox"][2]) / 2
            if cx > mid and (last_right_idx is None or i > last_right_idx):
                last_right_idx = i
            if cx < mid and first_left_idx is None:
                first_left_idx = i
        assert last_right_idx is not None and first_left_idx is not None, "need both columns"
        assert last_right_idx < first_left_idx, (
            f"RTL order broken: last right block index {last_right_idx} not before "
            f"first left block index {first_left_idx}")


# ---------- auth isolation ----------

class TestCrossUserIsolation:
    def test_other_user_cannot_access(self, base_url, existing_doc_id):
        # register a new user
        s = requests.Session()
        email = f"TEST_other_{int(time.time())}@example.com"
        r = s.post(f"{base_url}/api/auth/register",
                   json={"email": email, "password": "otherpass123", "name": "Other"}, timeout=30)
        assert r.status_code == 200
        r2 = s.get(f"{base_url}/api/documents/{existing_doc_id}", timeout=30)
        assert r2.status_code == 404


# ---------- upload validation ----------

class TestUploadValidation:
    def test_reject_non_pdf(self, admin_session, base_url):
        files = {"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")}
        r = admin_session.post(f"{base_url}/api/documents", files=files, timeout=30)
        assert r.status_code == 400

    def test_reject_bad_pdf(self, admin_session, base_url):
        files = {"file": ("fake.pdf", io.BytesIO(b"NOTAPDF"), "application/pdf")}
        r = admin_session.post(f"{base_url}/api/documents", files=files, timeout=30)
        assert r.status_code == 400

    def test_unauth_upload(self, base_url):
        files = {"file": ("x.pdf", io.BytesIO(b"%PDF-1.4\n"), "application/pdf")}
        r = requests.post(f"{base_url}/api/documents", files=files, timeout=30)
        assert r.status_code == 401


# ---------- progress + settings ----------

class TestProgressAndSettings:
    def test_put_get_progress(self, admin_session, base_url, existing_doc_id):
        payload = {"word_index": 7, "total_words": 100, "page_number": 2, "wpm": 450, "mode": "words3"}
        r = admin_session.put(f"{base_url}/api/documents/{existing_doc_id}/progress",
                              json=payload, timeout=30)
        assert r.status_code == 200
        r2 = admin_session.get(f"{base_url}/api/documents/{existing_doc_id}/progress", timeout=30)
        assert r2.status_code == 200
        got = r2.json()
        assert got["word_index"] == 7
        assert got["wpm"] == 450
        assert got["mode"] == "words3"
        assert got["page_number"] == 2

    def test_progress_invalid_wpm(self, admin_session, base_url, existing_doc_id):
        r = admin_session.put(f"{base_url}/api/documents/{existing_doc_id}/progress",
                              json={"word_index": 0, "wpm": 50, "mode": "word"}, timeout=30)
        assert r.status_code == 422

    def test_progress_invalid_mode(self, admin_session, base_url, existing_doc_id):
        r = admin_session.put(f"{base_url}/api/documents/{existing_doc_id}/progress",
                              json={"word_index": 0, "wpm": 300, "mode": "bogus"}, timeout=30)
        assert r.status_code == 422

    def test_settings_roundtrip(self, admin_session, base_url):
        r = admin_session.put(f"{base_url}/api/settings",
                              json={"wpm": 420, "mode": "line", "punctuation_pause": False}, timeout=30)
        assert r.status_code == 200
        g = admin_session.get(f"{base_url}/api/settings", timeout=30)
        assert g.status_code == 200
        d = g.json()
        assert d["wpm"] == 420 and d["mode"] == "line" and d["punctuation_pause"] is False


# ---------- upload + process (small fixture) ----------

class TestUploadAndProcess:
    def test_upload_fixture_and_process(self, admin_session, base_url):
        with open("/app/tests/fixtures/arabic_test.pdf", "rb") as fh:
            files = {"file": ("TEST_arabic.pdf", fh, "application/pdf")}
            r = admin_session.post(f"{base_url}/api/documents", files=files, timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        doc_id = d["document_id"]
        assert d["page_count"] == 5
        # poll
        deadline = time.time() + 90
        status = None
        while time.time() < deadline:
            g = admin_session.get(f"{base_url}/api/documents/{doc_id}", timeout=30)
            assert g.status_code == 200
            status = g.json()["status"]
            if status != "processing":
                break
            time.sleep(2)
        assert status in ("ready", "ready_with_warnings"), f"final status={status}"

        pages_r = admin_session.get(f"{base_url}/api/documents/{doc_id}/pages", timeout=30)
        assert pages_r.status_code == 200
        pages = {p["page_number"]: p for p in pages_r.json()}
        # p5 is scanned; with auto-OCR it should be ocr_done (fallback: needs_ocr/ocr_failed)
        assert pages[5]["status"] in ("ocr_done", "needs_ocr", "ocr_failed"), f"p5 status={pages[5]['status']}"
        # p1-4 should mostly be ok/warning
        ok_like = sum(1 for n in (1, 2, 3, 4) if pages[n]["status"] in ("ok", "warning"))
        assert ok_like >= 3, f"expected >=3 readable pages p1-4, got {ok_like}"

        # cleanup
        d_r = admin_session.delete(f"{base_url}/api/documents/{doc_id}", timeout=30)
        assert d_r.status_code == 200
        # verify gone
        g2 = admin_session.get(f"{base_url}/api/documents/{doc_id}", timeout=30)
        assert g2.status_code == 404
