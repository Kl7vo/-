"""Local Arabic OCR: Tesseract 5 (tessdata_best) + lexicon-assisted fixes for known OCR confusions. No paid API."""
import io
import re
import sqlite3
import threading
from functools import lru_cache
import unicodedata
from pathlib import Path

import pymupdf
import tesserocr
from PIL import Image
from tesserocr import OEM, PSM, RIL

from extraction import is_arabic, script_of

BASE = Path(__file__).parent
TESSDATA = str(BASE / "tessdata")
LEXICON_DB = BASE / "lexicon" / "ar_words.sqlite"
OCR_DPI = 300
OCR_ENGINE = f"tesseract-{tesserocr.tesseract_version().split()[1]}-ara-best"

# visually confusable letters in Tesseract's Arabic model (single substitution only)
CONFUSIONS = {
    "ئ": "ى", "ى": "ئي", "ة": "ه", "ه": "ة", "ث": "ت", "ت": "ث", "ق": "ف", "ف": "ق",
    "غ": "ع", "ع": "غ", "خ": "حج", "ح": "خج", "ج": "حخ", "ذ": "د", "د": "ذ", "ز": "ر", "ر": "ز",
    "ض": "ص", "ص": "ض", "ظ": "ط", "ط": "ظ", "ش": "س", "س": "ش", "ن": "ب", "ب": "ن",
}
SPURIOUS = set("ئىءـ")
LEAD_PUNCT = "«(\"'[{-–—"
TRAIL_PUNCT = "»)\"'.,،؛;:!?؟…]}-"

_lock = threading.Lock()
_api = None
_lexicon = None


_db_lock = threading.Lock()
_db = None


@lru_cache(maxsize=200_000)
def freq(word):
    global _db
    with _db_lock:
        if _db is None:
            _db = sqlite3.connect(f"file:{LEXICON_DB}?mode=ro", uri=True, check_same_thread=False)
        row = _db.execute("SELECT f FROM words WHERE w = ?", (word,)).fetchone()
    return row[0] if row else 0


def _api_instance():
    global _api
    if _api is None:
        _api = tesserocr.PyTessBaseAPI(path=TESSDATA, lang="ara", psm=PSM.AUTO, oem=OEM.LSTM_ONLY)
    return _api


def _bare(w):
    return "".join(c for c in w if not unicodedata.combining(c))


def _score(bare, doc_vocab):
    return (10 ** 9 if bare in doc_vocab else 0) + freq(bare)


def fix_punct(word, prev_has_open_quote, prefer_comma):
    """Tesseract's Arabic model almost never emits '،'; map its usual substitutes back."""
    if not word or not any(is_arabic(c) for c in word):
        return word, False
    tail = word[-1]
    if tail == "," or (tail == "»" and not prev_has_open_quote) or (tail == "؛" and prefer_comma):
        return word[:-1] + "،", True
    return word, False


def correct_word(word, doc_vocab, line_has_open_quote, prefer_comma=True):
    """Return (fixed_word, changed). Fixes only known OCR confusions, never style or spelling of real words."""
    word, changed = fix_punct(word, line_has_open_quote, prefer_comma)
    lead = len(word) - len(word.lstrip(LEAD_PUNCT))
    core_end = len(word.rstrip(TRAIL_PUNCT))
    pre, core, post = word[:lead], word[lead:core_end], word[core_end:]
    if not core or not any(is_arabic(c) for c in core):
        return word, changed
    bare = _bare(core)
    own = _score(bare, doc_vocab)
    if own >= 10 ** 9:
        return word, changed
    # trailing hamza misread for an Arabic comma: "البشرء" -> "البشر،"
    if bare.endswith("ء") and not post and own < 20 and _score(bare[:-1], doc_vocab) >= 50:
        return pre + core[:-1] + "،", True
    base_idx = [i for i, c in enumerate(core) if not unicodedata.combining(c)]
    best, best_score = None, 0
    for k, i in enumerate(base_idx):
        for alt in CONFUSIONS.get(core[i], ""):
            sc = _score(bare[:k] + alt + bare[k + 1:], doc_vocab)
            if sc > best_score:
                best, best_score = core[:i] + alt + core[i + 1:], sc
        # spurious extra glyph, e.g. "علئى" -> "على"
        if core[i] in SPURIOUS:
            sc = _score(bare[:k] + bare[k + 1:], doc_vocab)
            if sc > best_score:
                best, best_score = core[:i] + core[i + 1:], sc
    if best and (best_score >= 10 ** 9 and own < 50 or best_score >= max(20, 200 * own)):
        return pre + best + post, True
    if own == 0 and core.endswith("ئ"):
        return pre + core[:-1] + "ى" + post, True
    return word, changed


def ocr_page_blocks(pdf_bytes, index, doc_vocab=frozenset(), prefer_comma=True):
    """OCR one page. Returns blocks (with bboxes in PDF points), mean confidence and correction stats."""
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        page = doc[index]
        scale = 72.0 / OCR_DPI
        pix = page.get_pixmap(dpi=OCR_DPI, colorspace=pymupdf.csGRAY)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
    blocks, confs, low, fixed = [], [], 0, 0
    with _lock:
        api = _api_instance()
        api.SetImage(img)
        api.Recognize()
        it = api.GetIterator()
        cur_block, cur_line = None, None
        while it is not None:
            if it.Empty(RIL.WORD):
                if not it.Next(RIL.WORD):
                    break
                continue
            if cur_block is None or it.IsAtBeginningOf(RIL.BLOCK):
                cur_block = {"bbox": None, "lines": []}
                blocks.append(cur_block)
                cur_line = None
            if cur_line is None or it.IsAtBeginningOf(RIL.TEXTLINE):
                cur_line = {"words": [], "confs": [], "boxes": []}
                cur_block["lines"].append(cur_line)
            text = (it.GetUTF8Text(RIL.WORD) or "").strip()
            if text:
                # iterator words come in logical order but their code points are reversed for RTL text
                cur_line["words"].append(text[::-1] if any(is_arabic(c) for c in text) else text)
                cur_line["confs"].append(it.Confidence(RIL.WORD))
                cur_line["boxes"].append([v * scale for v in it.BoundingBox(RIL.WORD)])
            if not it.Next(RIL.WORD):
                break
    out_blocks = []
    for b in blocks:
        lines = []
        for ln in b["lines"]:
            if not ln["words"] or not ln["boxes"]:
                continue
            has_open = any("«" in w for w in ln["words"])
            words = []
            line_conf = sum(ln["confs"]) / len(ln["confs"]) if ln["confs"] else 0.0
            per_word = ln["confs"] if len(ln["confs"]) == len(ln["words"]) else [line_conf] * len(ln["words"])
            for w, c in zip(ln["words"], per_word):
                nw, ch = correct_word(w, doc_vocab, has_open, prefer_comma)
                fixed += ch
                low += c < 60
                confs.append(c)
                words.append(nw)
            boxes = ln["boxes"]
            bbox = [round(min(x[0] for x in boxes), 1), round(min(x[1] for x in boxes), 1),
                    round(max(x[2] for x in boxes), 1), round(max(x[3] for x in boxes), 1)]
            lines.append({"words": words, "scripts": [script_of(w) for w in words], "text": " ".join(words),
                          "bbox": bbox, "size": round((bbox[3] - bbox[1]) * 0.7, 2), "dir": "rtl",
                          "role": "body", "excluded": False, "furniture_confidence": 0.0,
                          "conf": round(line_conf, 1)})
        if lines:
            out_blocks.append({"bbox": [min(x["bbox"][0] for x in lines), min(x["bbox"][1] for x in lines),
                                        max(x["bbox"][2] for x in lines), max(x["bbox"][3] for x in lines)],
                               "lines": lines})
    mean = sum(confs) / len(confs) if confs else 0.0
    return {"blocks": out_blocks, "mean_conf": round(mean, 1), "low_conf_words": low, "corrections": fixed,
            "word_count": len(confs)}


def build_doc_vocab(pages):
    """Vocabulary from the document's own reliable text-layer pages."""
    vocab = set()
    for p in pages:
        for b in p["blocks"]:
            for ln in b["lines"]:
                for w in ln["words"]:
                    core = _bare(w.strip(LEAD_PUNCT + TRAIL_PUNCT))
                    if core and re.search(r"[\u0600-\u06FF]", core):
                        vocab.add(core)
    return vocab
