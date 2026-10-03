# PRD — قارئ: Arabic PDF Speed Reader (MVP)

## Original problem statement (summary)
Build the smallest version that proves the idea: upload an Arabic PDF, process it, extract page-linked text, read it at variable speeds (RSVP) with the ability to return to the original page. React RTL UI (upload, processing status, library, reader with word/3/5/line/2-lines modes, 100–5000 WPM, play/pause/forward/back/save position, original page view). FastAPI service (secure upload, processing job per file, text-PDF extraction, OCR page classification, per-page result + confidence, APIs for books/pages/words/progress/settings). MongoDB collections: users, documents, pages, text_blocks, reading_progress, processing_jobs. Extraction rules: keep original, page image/reference, no letter normalization/correction, coordinate + RTL ordering, repeated header/footer detection excluded only on high confidence, doubtful pages flagged for OCR/review. Each word inside a group keeps its own duration with punctuation pauses. Out of scope: public library, social, correction, TTS, mobile app.

## User choices
- OCR: Gemini 3 Flash (Emergent LLM key), on-demand (user-triggered)
- Auth: JWT email/password AND Emergent Google login
- Storage: Emergent Object Storage; max 50 MB

## Architecture
- backend/server.py (routes, background processing + OCR jobs), extraction.py (PyMuPDF rawdict → visual glyph ordering → logical RTL/bidi runs, columns, furniture, footnotes, page assessment), auth.py, storage.py, ocr.py, db.py
- frontend: Login, Library, DocumentStatus, Reader (+ useRsvp engine, rsvp.js grouping/timing, PageCompare panel)

## Implemented (2026-10-03)
- JWT + Google auth, admin seed, brute-force lockout
- Upload validation (PDF magic, size, encryption, page limit), original stored in object storage
- Extraction: glyph x-position ordering, mark attachment, mixed Arabic/English/number run reordering, mirrored bracket fix, presentation-form decoding only, bidi controls stripped
- Two-column detection (right column first), header/footer detection (excluded ≥0.75 confidence), footnote tagging
- Page status: ok / warning / needs_ocr / empty / ocr_done / ocr_failed with confidence + issues (broken encoding, fragmented words, scanned, mixed)
- On-demand Gemini OCR per page or all flagged pages; known furniture excluded on OCR pages
- Lazy page image rendering cached to object storage; compare original vs extracted text (excluded lines struck-through)
- RSVP reader: 5 modes, 100–5000 WPM, per-word durations, punctuation pause toggle, page nav, auto/ manual save, resume, keyboard shortcuts, warning banners and auto-pause markers for unreadable pages
- Delete document (removes pages/blocks/progress/jobs; storage soft)
- Tests: /app/backend/tests/test_backend.py (23 pass), fixture /app/tests/fixtures/arabic_test.pdf

## Iteration 2 (2026-10-03)
- Fixed InDesign ligature bug (في→يف, لا→ال, الله→هلل): MuPDF zero-width multi-char glyph grouping + per-page/document lam-alef vote for ligature orientation (extractor_version 2)
- Reprocess endpoint/button (keeps OCR pages + cached images); user book reprocessed
- Reader index sheet: bookmarks (add via button / B key, jump, delete, ticks on progress bar), PDF outline or auto-detected headings TOC, page list
- Storage retries on 5xx/429

## Iteration 3 (2026-10-03) — zero-credit OCR
- Removed Gemini OCR. Local Tesseract 5.5.1 (pip tesserocr wheel, tessdata_best ara in backend/tessdata) — no paid API, no LLM key
- Lexicon-assisted OCR confusion fixes (ى/ئ, comma variants, similar letters, spurious glyphs) using backend/lexicon/ar_words.sqlite (828k words, CC-BY-SA FrequencyWords) + document vocabulary
- Scanned / broken-encoding pages OCR'd automatically during processing (stage 'ocr'); bboxes kept so header/footer detection works on OCR pages
- Benchmark on user's book: CER ~5.5% incl. diacritics, ~3% without (bench_local.py); extractor_version 3

## Iteration 4 — self-hosting
- STORAGE_DIR env → local-disk storage (no Emergent storage); COOKIE_SECURE env; REACT_APP_DISABLE_GOOGLE_AUTH flag
- Dockerfiles (backend, frontend+nginx), docker-compose.yml (mongo+backend+frontend), selfhost.env.example, SELF_HOSTING.md, backend/requirements.selfhost.txt

## Backlog
- P0: test on user's real PDFs; tables, heavy tashkeel, footnote-heavy scans
- P1: OCR review/edit UI with side-by-side diff; re-run extraction; per-line confidence highlighting in reader
- P1: Storage hard-delete/retention policy, rate limiting on OCR, job queue that survives restarts
- P2: Reading stats, bookmarks, search inside document
