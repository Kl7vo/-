import asyncio
import logging
import os
import statistics
import uuid
from datetime import datetime, timezone
from typing import List, Literal, Optional

import pymupdf
from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

import storage
from auth import get_current_user, router as auth_router, seed_admin
from db import client, db
from extraction import (_furniture_key, apply_known_furniture, assess_page, detect_furniture, extract_page,
                        mark_footnotes, page_text, render_png)
from ocr import OCR_ENGINE, build_doc_vocab, ocr_page_blocks
from security import apply_security_headers, validate_pdf_content

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("reader")

MAX_BYTES = int(os.environ["MAX_UPLOAD_MB"]) * 1024 * 1024
MAX_PAGES = int(os.environ["MAX_PAGES"])
# Bound rasterization cost as well as upload bytes/pages (PDFs can contain huge pages).
MAX_PAGE_PIXELS = int(os.environ.get("MAX_PAGE_PIXELS", "50000000"))
EXTRACTOR_VERSION = 3
OCR_SLOTS = asyncio.Semaphore(1)
_tasks = set()

app = FastAPI(docs_url=None if os.environ.get("DISABLE_API_DOCS", "true").lower() == "true" else "/docs",
              redoc_url=None)
api = APIRouter(prefix="/api")


@api.get("/health")
async def health():
    return {"status": "ok"}


def _cors_origins():
    raw = os.environ.get("CORS_ORIGINS", "")
    return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip() and origin.strip() != "*"]


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    # Cookie-authenticated state changes must carry a same-origin Origin (or be a
    # non-browser client without Origin). This blocks cross-site form/fetch CSRF.
    if request.method not in {"GET", "HEAD", "OPTIONS", "TRACE"} and any(
            request.cookies.get(name) for name in ("access_token", "refresh_token", "session_token")):
        origin = request.headers.get("origin")
        allowed = _cors_origins()
        if origin and (origin.rstrip("/") not in allowed):
            return JSONResponse(status_code=403, content={"detail": "طلب cross-site مرفوض"})
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse(status_code=403, content={"detail": "طلب cross-site مرفوض"})
    response = await call_next(request)
    return apply_security_headers(response, request)


def now():
    return datetime.now(timezone.utc)


def spawn(coro):
    t = asyncio.create_task(coro)
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)


async def user_dep(request: Request) -> dict:
    return await get_current_user(request)


async def own_doc(document_id: str, user: dict) -> dict:
    doc = await db.documents.find_one({"document_id": document_id, "user_id": user["user_id"], "is_deleted": False},
                                      {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="الملف غير موجود")
    return doc


async def refresh_doc_stats(document_id: str):
    counts = {}
    async for p in db.pages.find({"document_id": document_id}, {"_id": 0, "status": 1}):
        counts[p["status"]] = counts.get(p["status"], 0) + 1
    total = sum(counts.values())
    readable = counts.get("ok", 0) + counts.get("warning", 0) + counts.get("ocr_done", 0)
    flagged = counts.get("needs_ocr", 0) + counts.get("ocr_failed", 0) + counts.get("warning", 0)
    if total and readable == 0:
        status = "extraction_failed"
    elif flagged or counts.get("ocr_done", 0):
        status = "ready_with_warnings"
    else:
        status = "ready"
    await db.documents.update_one({"document_id": document_id},
                                  {"$set": {"page_stats": counts, "status": status, "updated_at": now()}})


async def save_page_blocks(document_id: str, page_number: int, blocks: list, source: str):
    await db.text_blocks.update_many({"document_id": document_id, "page_number": page_number, "active": True},
                                     {"$set": {"active": False}})
    docs = []
    for i, b in enumerate(blocks):
        lines = [{k: v for k, v in ln.items() if k != "scripts"} for ln in b["lines"]]
        docs.append({"block_id": uuid.uuid4().hex, "document_id": document_id, "page_number": page_number,
                     "block_index": i, "source": source, "active": True, "bbox": b["bbox"], "lines": lines,
                     "created_at": now()})
    if docs:
        await db.text_blocks.insert_many(docs)


def _counts(blocks):
    words = [w for b in blocks for ln in b["lines"] if not ln.get("excluded") for w in ln["words"]]
    return len(words), sum(len(w) for w in words), sum(1 for b in blocks for ln in b["lines"] if ln.get("excluded"))


def _auto_toc(pages):
    """Fallback index: short lines set in a clearly larger font than the body text."""
    sizes = [ln["size"] for p in pages for b in p["blocks"] for ln in b["lines"] if ln.get("role") == "body" and ln["size"]]
    if not sizes:
        return []
    body = statistics.median(sizes)
    toc = []
    for p in pages:
        for b in p["blocks"]:
            for ln in b["lines"]:
                if ln.get("role") == "body" and ln["size"] >= 1.3 * body and len(ln["words"]) <= 12:
                    if toc and toc[-1]["page"] == p["page_number"] and toc[-1]["_y"] >= ln["bbox"][1] - 2 * ln["size"]:
                        toc[-1]["title"] += " " + ln["text"]
                        toc[-1]["_y"] = ln["bbox"][1]
                        continue
                    toc.append({"level": 1, "title": ln["text"], "page": p["page_number"], "auto": True, "_y": ln["bbox"][1]})
    for t in toc:
        t.pop("_y")
        t["title"] = t["title"][:200]
    return toc[:400]


def _read_toc(pdf):
    try:
        return [{"level": lvl, "title": title.strip()[:200], "page": page} for lvl, title, page, *_ in pdf.get_toc()
                if title.strip() and page >= 1]
    except Exception:
        return []


def _ocr_verdict(r):
    if not r["word_count"]:
        return "empty", 0.0, ["ocr_no_text"]
    issues = ["ocr_unverified"]
    if r["mean_conf"] < 70:
        issues.append("ocr_low_confidence")
    if r["low_conf_words"]:
        issues.append("ocr_unreadable_words")
    return "ocr_done", round(min(0.9, r["mean_conf"] / 100), 2), issues


def _ocr_context(pages):
    """Vocabulary and punctuation habits learned from the document's reliable text pages."""
    good = [p for p in pages if p.get("_pre") in ("ok", "warning")]
    text = "".join(ln["text"] for p in good for b in p["blocks"] for ln in b["lines"])
    commas, semis = text.count("،"), text.count("؛")
    return build_doc_vocab(good), (commas + semis < 20) or semis <= 0.3 * commas


async def _ocr_one(pdf_bytes, index, vocab, prefer_comma):
    async with OCR_SLOTS:
        return await asyncio.to_thread(ocr_page_blocks, pdf_bytes, index, vocab, prefer_comma)


async def process_document(document_id: str, job_id: str, pdf_bytes: bytes):
    try:
        pdf = await asyncio.to_thread(pymupdf.open, stream=pdf_bytes, filetype="pdf")
        n = pdf.page_count
        await db.processing_jobs.update_one({"job_id": job_id}, {"$set": {
            "status": "running", "stage": "extract", "total": n, "progress": 0, "started_at": now()}})
        toc = _read_toc(pdf)
        pages, rev, log = [], 0, 0
        for i in range(n):
            hint = (rev > log) if (rev or log) else None
            try:
                res = await asyncio.to_thread(extract_page, pdf, i, hint)
                rev += res["stats"].get("lig_votes_reversed", 0)
                log += res["stats"].get("lig_votes_logical", 0)
            except Exception as e:
                logger.exception("page %s failed", i + 1)
                res = {"width": 0, "height": 0, "blocks": [], "two_columns": False, "image_coverage": 1.0,
                       "stats": {}, "error": str(e)[:200]}
            res["page_number"] = i + 1
            res["_pre"] = "needs_ocr" if res.get("error") else assess_page(res)[0]
            pages.append(res)
            if i % 3 == 0 or i == n - 1:
                await db.processing_jobs.update_one({"job_id": job_id}, {"$set": {"progress": i + 1}})
        pdf.close()
        previous = {p["page_number"]: p async for p in db.pages.find({"document_id": document_id}, {"_id": 0})}
        ocr_pages = {k for k, v in previous.items() if v.get("source") == "ocr"}
        # free local OCR for pages without a trustworthy text layer
        todo = [p for p in pages if p["_pre"] == "needs_ocr" and p["page_number"] not in ocr_pages]
        if todo:
            vocab, prefer_comma = _ocr_context(pages)
            await db.processing_jobs.update_one({"job_id": job_id}, {"$set": {
                "stage": "ocr", "progress": 0, "total": len(todo)}})
            for k, p in enumerate(todo):
                try:
                    r = await _ocr_one(pdf_bytes, p["page_number"] - 1, vocab, prefer_comma)
                    p["blocks"], p["ocr"] = r["blocks"], r
                except Exception as e:
                    logger.exception("local OCR failed on page %s", p["page_number"])
                    p["ocr_error"] = str(e)[:200]
                await db.processing_jobs.update_one({"job_id": job_id}, {"$set": {"progress": k + 1}})
        await db.processing_jobs.update_one({"job_id": job_id}, {"$set": {"stage": "analyze"}})
        detect_furniture(pages)
        await db.pages.delete_many({"document_id": document_id})
        await db.text_blocks.delete_many({"document_id": document_id, "$or": [
            {"source": {"$ne": "ocr"}}, {"page_number": {"$nin": list(ocr_pages)}}]})
        for p in pages:
            pn = p["page_number"]
            if pn in ocr_pages:
                await db.pages.insert_one(previous[pn])
                continue
            mark_footnotes(p)
            source, extra = "text", {}
            if p.get("ocr"):
                source = "ocr"
                status, conf, issues = _ocr_verdict(p["ocr"])
                extra = {"ocr_engine": OCR_ENGINE, "ocr_mean_conf": p["ocr"]["mean_conf"],
                         "ocr_fixes": p["ocr"]["corrections"], "ocr_at": now()}
            elif p.get("ocr_error"):
                status, conf, issues = "ocr_failed", 0.0, ["ocr_error"]
            else:
                status, conf, issues = assess_page(p)
            if p.get("error") and not p.get("ocr"):
                status, conf, issues = "needs_ocr", 0.0, ["extraction_error"]
            wc, cc, excl = _counts(p["blocks"])
            await db.pages.insert_one({
                "document_id": document_id, "page_number": pn, "width": p["width"],
                "height": p["height"], "status": status, "confidence": conf, "issues": issues, "source": source,
                "word_count": wc, "char_count": cc, "excluded_lines": excl, "two_columns": p["two_columns"],
                "image_coverage": round(p["image_coverage"], 3), "stats": p["stats"],
                "image_path": previous.get(pn, {}).get("image_path"), "created_at": now(), **extra})
            await save_page_blocks(document_id, pn, p["blocks"], source)
        if not toc:
            toc = _auto_toc(pages)
        await db.documents.update_one({"document_id": document_id}, {"$set": {
            "toc": toc, "ligatures_reversed": rev > log, "extractor_version": EXTRACTOR_VERSION}})
        await refresh_doc_stats(document_id)
        await db.processing_jobs.update_one({"job_id": job_id}, {"$set": {
            "status": "done", "stage": "done", "finished_at": now()}})
    except Exception as e:
        logger.exception("processing failed")
        await db.processing_jobs.update_one({"job_id": job_id}, {"$set": {
            "status": "failed", "error": str(e)[:300], "finished_at": now()}})
        await db.documents.update_one({"document_id": document_id}, {"$set": {"status": "failed"}})


async def _text_pages_context(document_id):
    known, words, commas, semis = set(), set(), 0, 0
    async for b in db.text_blocks.find({"document_id": document_id, "active": True, "source": "text"},
                                       {"_id": 0, "lines": 1}):
        for ln in b["lines"]:
            if ln.get("excluded"):
                known.add(_furniture_key(ln["text"]))
                continue
            commas += ln["text"].count("،")
            semis += ln["text"].count("؛")
            words.update(ln["words"])
    vocab = build_doc_vocab([{"blocks": [{"lines": [{"words": list(words)}]}]}])
    return known, vocab, (commas + semis < 20) or semis <= 0.3 * commas


async def run_ocr(document_id: str, job_id: str, storage_path: str, page_numbers: List[int]):
    await db.processing_jobs.update_one({"job_id": job_id}, {"$set": {"status": "running", "stage": "ocr",
                                                                      "started_at": now()}})
    failures = 0
    try:
        pdf_bytes = await asyncio.to_thread(storage.get_pdf_bytes, document_id, storage_path)
        known, vocab, prefer_comma = await _text_pages_context(document_id)
        for i, pn in enumerate(page_numbers):
            try:
                r = await _ocr_one(pdf_bytes, pn - 1, vocab, prefer_comma)
                blocks = r["blocks"]
                apply_known_furniture(blocks, known)
                await save_page_blocks(document_id, pn, blocks, "ocr")
                status, conf, issues = _ocr_verdict(r)
                wc, cc, excl = _counts(blocks)
                await db.pages.update_one({"document_id": document_id, "page_number": pn}, {"$set": {
                    "status": status, "confidence": conf, "issues": issues, "source": "ocr",
                    "word_count": wc, "char_count": cc, "excluded_lines": excl, "ocr_engine": OCR_ENGINE,
                    "ocr_mean_conf": r["mean_conf"], "ocr_fixes": r["corrections"], "ocr_at": now()}})
            except Exception as e:
                failures += 1
                logger.exception("OCR failed for page %s", pn)
                await db.pages.update_one({"document_id": document_id, "page_number": pn}, {"$set": {
                    "status": "ocr_failed", "issues": ["ocr_error"], "ocr_error": str(e)[:200]}})
            await db.processing_jobs.update_one({"job_id": job_id}, {"$set": {"progress": i + 1}})
        await refresh_doc_stats(document_id)
        await db.processing_jobs.update_one({"job_id": job_id}, {"$set": {
            "status": "done" if failures == 0 else "done_with_errors", "stage": "done", "failures": failures,
            "finished_at": now()}})
    except Exception as e:
        logger.exception("OCR job failed")
        await db.processing_jobs.update_one({"job_id": job_id}, {"$set": {
            "status": "failed", "error": str(e)[:300], "finished_at": now()}})


def _job_out(job):
    if not job:
        return None
    return {k: job.get(k) for k in ("job_id", "type", "status", "stage", "progress", "total", "error", "failures")}


@api.get("/")
async def root():
    return {"message": "Arabic RSVP Reader API"}


@api.post("/documents")
async def upload_document(file: UploadFile = File(...), user: dict = Depends(user_dep)):
    name = file.filename or "document.pdf"
    if not name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="يُسمح بملفات PDF فقط")
    chunks, size = [], 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > MAX_BYTES:
            raise HTTPException(status_code=413, detail=f"حجم الملف يتجاوز {MAX_BYTES // (1024 * 1024)} ميغابايت")
        chunks.append(chunk)
    data = b"".join(chunks)
    if not data.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="الملف ليس PDF صالحاً")
    validate_pdf_content(data)
    try:
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            if pdf.needs_pass:
                raise HTTPException(status_code=400, detail="الملف محمي بكلمة مرور")
            page_count = pdf.page_count
            if page_count == 0 or page_count > MAX_PAGES:
                raise HTTPException(status_code=400, detail=f"عدد الصفحات يجب أن يكون بين 1 و {MAX_PAGES}")
            for page in pdf:
                # OCR at 300 DPI can amplify a very large page into a memory/CPU DoS.
                pixels = page.rect.width * page.rect.height * (300 / 72) ** 2
                if pixels > MAX_PAGE_PIXELS:
                    raise HTTPException(status_code=400, detail="أبعاد إحدى صفحات PDF كبيرة جداً")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="تعذّر فتح ملف PDF (قد يكون تالفاً)")
    document_id = uuid.uuid4().hex
    path = f"{storage.APP_NAME}/uploads/{user['user_id']}/{document_id}.pdf"
    try:
        result = await asyncio.to_thread(storage.put_object, path, data, "application/pdf")
    except Exception:
        logger.exception("storage upload failed")
        raise HTTPException(status_code=503, detail="فشل تخزين الملف. حاول مجدداً")
    storage.cache_pdf(document_id, data)
    title = name[:-4] if name.lower().endswith(".pdf") else name
    await db.documents.insert_one({
        "document_id": document_id, "user_id": user["user_id"], "title": title[:200], "original_filename": name,
        "storage_path": result["path"], "size": size, "page_count": page_count, "status": "processing",
        "page_stats": {}, "is_deleted": False, "created_at": now(), "updated_at": now()})
    job_id = uuid.uuid4().hex
    await db.processing_jobs.insert_one({"job_id": job_id, "document_id": document_id, "user_id": user["user_id"],
                                         "type": "extract", "status": "queued", "progress": 0,
                                         "total": page_count, "created_at": now()})
    spawn(process_document(document_id, job_id, data))
    return {"document_id": document_id, "job_id": job_id, "page_count": page_count}


@api.get("/documents")
async def list_documents(user: dict = Depends(user_dep)):
    docs = await db.documents.find({"user_id": user["user_id"], "is_deleted": False},
                                   {"_id": 0, "storage_path": 0, "toc": 0}).sort("created_at", -1).to_list(500)
    progress = {p["document_id"]: p async for p in db.reading_progress.find({"user_id": user["user_id"]}, {"_id": 0})}
    for d in docs:
        p = progress.get(d["document_id"])
        d["progress"] = {"word_index": p["word_index"], "total_words": p.get("total_words", 0),
                         "page_number": p.get("page_number", 1)} if p else None
    return docs


@api.get("/documents/{document_id}")
async def get_document(document_id: str, user: dict = Depends(user_dep)):
    doc = await own_doc(document_id, user)
    doc.pop("storage_path", None)
    job = await db.processing_jobs.find_one({"document_id": document_id}, {"_id": 0}, sort=[("created_at", -1)])
    doc["job"] = _job_out(job)
    return doc


@api.delete("/documents/{document_id}")
async def delete_document(document_id: str, user: dict = Depends(user_dep)):
    await own_doc(document_id, user)
    await db.documents.update_one({"document_id": document_id}, {"$set": {"is_deleted": True, "deleted_at": now()}})
    for coll in (db.pages, db.text_blocks, db.reading_progress, db.processing_jobs, db.bookmarks):
        await coll.delete_many({"document_id": document_id})
    storage.drop_cache(document_id)
    return {"ok": True}


@api.get("/documents/{document_id}/pages")
async def list_pages(document_id: str, user: dict = Depends(user_dep)):
    await own_doc(document_id, user)
    return await db.pages.find({"document_id": document_id},
                               {"_id": 0, "stats": 0, "image_path": 0}).sort("page_number", 1).to_list(5000)


@api.get("/documents/{document_id}/pages/{page_number}")
async def get_page(document_id: str, page_number: int, user: dict = Depends(user_dep)):
    await own_doc(document_id, user)
    page = await db.pages.find_one({"document_id": document_id, "page_number": page_number},
                                   {"_id": 0, "image_path": 0})
    if not page:
        raise HTTPException(status_code=404, detail="الصفحة غير موجودة")
    blocks = await db.text_blocks.find({"document_id": document_id, "page_number": page_number, "active": True},
                                       {"_id": 0}).sort("block_index", 1).to_list(1000)
    page["blocks"] = blocks
    page["text"] = page_text(blocks)
    return page


@api.get("/documents/{document_id}/pages/{page_number}/image")
async def page_image(document_id: str, page_number: int, user: dict = Depends(user_dep)):
    doc = await own_doc(document_id, user)
    if page_number < 1 or page_number > doc["page_count"]:
        raise HTTPException(status_code=404, detail="الصفحة غير موجودة")
    page = await db.pages.find_one({"document_id": document_id, "page_number": page_number}, {"_id": 0})
    headers = {"Cache-Control": "private, max-age=3600"}
    if page and page.get("image_path"):
        try:
            data = await asyncio.to_thread(storage.get_object, page["image_path"])
            return Response(content=data, media_type="image/png", headers=headers)
        except Exception:
            logger.warning("cached page image missing, re-rendering")
    pdf_bytes = await asyncio.to_thread(storage.get_pdf_bytes, document_id, doc["storage_path"])
    png = await asyncio.to_thread(render_png, pdf_bytes, page_number - 1, 110)
    path = f"{storage.APP_NAME}/pages/{user['user_id']}/{document_id}/{page_number}.png"
    try:
        res = await asyncio.to_thread(storage.put_object, path, png, "image/png")
        await db.pages.update_one({"document_id": document_id, "page_number": page_number},
                                  {"$set": {"image_path": res["path"]}})
    except Exception:
        logger.warning("page image upload failed")
    return Response(content=png, media_type="image/png", headers=headers)


@api.get("/documents/{document_id}/content")
async def get_content(document_id: str, user: dict = Depends(user_dep)):
    await own_doc(document_id, user)
    pages = await db.pages.find({"document_id": document_id},
                                {"_id": 0, "page_number": 1, "status": 1, "confidence": 1, "issues": 1,
                                 "source": 1}).sort("page_number", 1).to_list(5000)
    by_page = {p["page_number"]: [] for p in pages}
    cursor = db.text_blocks.find({"document_id": document_id, "active": True},
                                 {"_id": 0, "page_number": 1, "lines.words": 1, "lines.role": 1,
                                  "lines.excluded": 1, "block_index": 1}).sort([("page_number", 1),
                                                                                 ("block_index", 1)])
    async for b in cursor:
        by_page.setdefault(b["page_number"], []).extend(
            {"w": ln["words"], "r": ln.get("role", "body")} for ln in b["lines"] if not ln.get("excluded"))
    for p in pages:
        p["lines"] = by_page.get(p["page_number"], [])
    return {"pages": pages}


@api.get("/documents/{document_id}/words")
async def get_words(document_id: str, page: int, user: dict = Depends(user_dep)):
    await own_doc(document_id, user)
    blocks = await db.text_blocks.find({"document_id": document_id, "page_number": page, "active": True},
                                       {"_id": 0}).sort("block_index", 1).to_list(1000)
    words = []
    for b in blocks:
        for li, ln in enumerate(b["lines"]):
            if ln.get("excluded"):
                continue
            words += [{"text": w, "page": page, "block": b["block_index"], "line": li} for w in ln["words"]]
    return {"page": page, "words": words}


class OcrIn(BaseModel):
    pages: Optional[List[int]] = None


@api.post("/documents/{document_id}/ocr")
async def start_ocr(document_id: str, body: OcrIn, user: dict = Depends(user_dep)):
    doc = await own_doc(document_id, user)
    running = await db.processing_jobs.find_one({"document_id": document_id, "status": {"$in": ["queued", "running"]}})
    if running:
        raise HTTPException(status_code=409, detail="توجد مهمة معالجة قيد التنفيذ")
    if body.pages:
        allowed = {p["page_number"] async for p in db.pages.find(
            {"document_id": document_id, "status": {"$in": ["needs_ocr", "ocr_failed", "warning", "empty"]}},
            {"page_number": 1})}
        targets = sorted({p for p in body.pages if p in allowed})
    else:
        targets = [p["page_number"] async for p in db.pages.find(
            {"document_id": document_id, "status": {"$in": ["needs_ocr", "ocr_failed"]}}, {"page_number": 1})]
    if not targets:
        raise HTTPException(status_code=400, detail="لا توجد صفحات تحتاج OCR")
    if len(targets) > MAX_PAGES:
        raise HTTPException(status_code=400, detail="عدد الصفحات كبير جداً")
    job_id = uuid.uuid4().hex
    await db.processing_jobs.insert_one({"job_id": job_id, "document_id": document_id, "user_id": user["user_id"],
                                         "type": "ocr", "status": "queued", "progress": 0, "total": len(targets),
                                         "pages": targets, "created_at": now()})
    spawn(run_ocr(document_id, job_id, doc["storage_path"], targets))
    return {"job_id": job_id, "pages": targets}


@api.post("/documents/{document_id}/reprocess")
async def reprocess_document(document_id: str, user: dict = Depends(user_dep)):
    doc = await own_doc(document_id, user)
    if await db.processing_jobs.find_one({"document_id": document_id, "status": {"$in": ["queued", "running"]}}):
        raise HTTPException(status_code=409, detail="توجد مهمة معالجة قيد التنفيذ")
    try:
        data = await asyncio.to_thread(storage.get_pdf_bytes, document_id, doc["storage_path"])
    except Exception:
        raise HTTPException(status_code=503, detail="تعذّر جلب الملف الأصلي. حاول مجدداً")
    job_id = uuid.uuid4().hex
    await db.processing_jobs.insert_one({"job_id": job_id, "document_id": document_id, "user_id": user["user_id"],
                                         "type": "extract", "status": "queued", "progress": 0,
                                         "total": doc["page_count"], "created_at": now()})
    await db.documents.update_one({"document_id": document_id}, {"$set": {"status": "processing"}})
    spawn(process_document(document_id, job_id, data))
    return {"job_id": job_id}


@api.get("/documents/{document_id}/toc")
async def get_toc(document_id: str, user: dict = Depends(user_dep)):
    doc = await own_doc(document_id, user)
    if "toc" not in doc:
        pdf_bytes = await asyncio.to_thread(storage.get_pdf_bytes, document_id, doc["storage_path"])
        pdf = await asyncio.to_thread(pymupdf.open, stream=pdf_bytes, filetype="pdf")
        doc["toc"] = _read_toc(pdf)
        pdf.close()
        await db.documents.update_one({"document_id": document_id}, {"$set": {"toc": doc["toc"]}})
    return {"toc": doc["toc"]}


class BookmarkIn(BaseModel):
    word_index: int = Field(ge=0)
    page_number: int = Field(ge=1)
    snippet: str = Field(default="", max_length=300)
    note: str = Field(default="", max_length=500)


@api.get("/documents/{document_id}/bookmarks")
async def list_bookmarks(document_id: str, user: dict = Depends(user_dep)):
    await own_doc(document_id, user)
    return await db.bookmarks.find({"document_id": document_id, "user_id": user["user_id"]},
                                   {"_id": 0}).sort("word_index", 1).to_list(1000)


@api.post("/documents/{document_id}/bookmarks")
async def add_bookmark(document_id: str, body: BookmarkIn, user: dict = Depends(user_dep)):
    await own_doc(document_id, user)
    bm = {"bookmark_id": uuid.uuid4().hex, "document_id": document_id, "user_id": user["user_id"],
          **body.model_dump(), "created_at": now().isoformat()}
    await db.bookmarks.insert_one(bm)
    bm.pop("_id", None)
    return bm


@api.delete("/documents/{document_id}/bookmarks/{bookmark_id}")
async def delete_bookmark(document_id: str, bookmark_id: str, user: dict = Depends(user_dep)):
    res = await db.bookmarks.delete_one({"bookmark_id": bookmark_id, "document_id": document_id,
                                         "user_id": user["user_id"]})
    if not res.deleted_count:
        raise HTTPException(status_code=404, detail="العلامة غير موجودة")
    return {"ok": True}


ModeT = Literal["word", "words3", "words5", "line", "lines2"]


class ProgressIn(BaseModel):
    word_index: int = Field(ge=0)
    total_words: int = Field(ge=0, default=0)
    page_number: int = Field(ge=1, default=1)
    wpm: int = Field(ge=100, le=5000, default=300)
    mode: ModeT = "word"


@api.get("/documents/{document_id}/progress")
async def get_progress(document_id: str, user: dict = Depends(user_dep)):
    await own_doc(document_id, user)
    p = await db.reading_progress.find_one({"document_id": document_id, "user_id": user["user_id"]}, {"_id": 0})
    return p or {"word_index": 0, "page_number": 1, "wpm": None, "mode": None}


@api.put("/documents/{document_id}/progress")
async def put_progress(document_id: str, body: ProgressIn, user: dict = Depends(user_dep)):
    await own_doc(document_id, user)
    data = body.model_dump()
    data.update({"document_id": document_id, "user_id": user["user_id"], "updated_at": now()})
    await db.reading_progress.update_one({"document_id": document_id, "user_id": user["user_id"]},
                                         {"$set": data}, upsert=True)
    return {"ok": True}


class SettingsIn(BaseModel):
    wpm: int = Field(ge=100, le=5000)
    mode: ModeT
    punctuation_pause: bool = True


DEFAULT_SETTINGS = {"wpm": 300, "mode": "word", "punctuation_pause": True}


@api.get("/settings")
async def get_settings(user: dict = Depends(user_dep)):
    return user.get("reading_settings") or DEFAULT_SETTINGS


@api.put("/settings")
async def put_settings(body: SettingsIn, user: dict = Depends(user_dep)):
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"reading_settings": body.model_dump()}})
    return body.model_dump()


app.include_router(auth_router)
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=_cors_origins(),
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
)


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id", unique=True)
    await db.login_attempts.create_index("identifier")
    await db.user_sessions.create_index("session_token")
    await db.documents.create_index([("user_id", 1), ("created_at", -1)])
    await db.documents.create_index("document_id", unique=True)
    await db.pages.create_index([("document_id", 1), ("page_number", 1)], unique=True)
    await db.text_blocks.create_index([("document_id", 1), ("page_number", 1), ("active", 1), ("block_index", 1)])
    await db.reading_progress.create_index([("document_id", 1), ("user_id", 1)], unique=True)
    await db.processing_jobs.create_index([("document_id", 1), ("created_at", -1)])
    await db.bookmarks.create_index([("document_id", 1), ("user_id", 1), ("word_index", 1)])
    await seed_admin()
    await db.processing_jobs.update_many({"status": {"$in": ["queued", "running"]}},
                                         {"$set": {"status": "failed", "error": "انقطعت المعالجة بسبب إعادة تشغيل الخادم"}})
    try:
        await asyncio.to_thread(storage.init_storage)
        logger.info("Storage initialized")
    except Exception as e:
        logger.error(f"Storage init failed: {e}")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
