"""Arabic-aware PDF text extraction: coordinates + RTL ordering, no letter normalization."""
import re
import statistics
import unicodedata
from collections import defaultdict

import pymupdf

FLAGS = (pymupdf.TEXT_PRESERVE_LIGATURES | pymupdf.TEXT_PRESERVE_WHITESPACE | pymupdf.TEXT_MEDIABOX_CLIP
         | pymupdf.TEXT_INHIBIT_SPACES)
MIRROR = {")": "(", "]": "[", "}": "{", ">": "<", "»": "«"}

ARABIC_RANGES = ((0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF))
PRESENTATION_RANGES = ((0xFB50, 0xFDFF), (0xFE70, 0xFEFF))
ARABIC_DIGITS = set("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹")
BIDI_CONTROLS = set("\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\u061c")
SENTENCE_END = set(".!?؟…۔")
SINGLE_LETTER_OK = {"و", "ف", "ب", "ك", "ل", "أ", "ء"}


def _in(cp, ranges):
    return any(a <= cp <= b for a, b in ranges)


def is_arabic(ch):
    return _in(ord(ch), ARABIC_RANGES) and ch not in ARABIC_DIGITS and unicodedata.category(ch)[0] in "LM"


def is_latin(ch):
    return ch.isalpha() and not _in(ord(ch), ARABIC_RANGES)


def is_digit(ch):
    return ch.isdigit() or ch in ARABIC_DIGITS


def is_bad(ch):
    cp = ord(ch)
    return ch == "\ufffd" or 0xE000 <= cp <= 0xF8FF or (unicodedata.category(ch) == "Cc" and ch not in "\t\n\r")


def script_of(text):
    if any(is_arabic(c) for c in text):
        return "R"
    if any(is_latin(c) for c in text):
        return "L"
    if any(is_digit(c) for c in text):
        return "N"
    return "O"


def _cx(ch):
    return (ch["bbox"][0] + ch["bbox"][2]) / 2


def _decode(c, stats):
    if _in(ord(c), PRESENTATION_RANGES):
        stats["presentation_chars"] += 1
        return unicodedata.normalize("NFKC", c)
    return c


ALEFS = set("اأإآٱ")


def glyph_units(chars, size):
    """Group chars emitted for one multi-char glyph (ligatures such as لا / في / لله).

    MuPDF emits the extra chars of a glyph as zero-width chars sitting on the glyph edge.
    """
    units, pending = [], []

    def flush():
        units.extend({"raw": [p], "bbox": p["bbox"], "multi": False} for p in pending)
        pending.clear()

    for ch in chars:
        c = ch["c"]
        w = ch["bbox"][2] - ch["bbox"][0]
        if unicodedata.combining(c):
            units.append({"raw": [ch], "bbox": ch["bbox"], "multi": False, "mark": True})
            continue
        if w <= 0.02 * size and not c.isspace():
            if pending and abs(pending[0]["bbox"][0] - ch["bbox"][0]) > 0.15:
                flush()
            pending.append(ch)
            continue
        if (pending and w > 0.05 * size and is_arabic(c) and all(is_arabic(p["c"]) for p in pending)
                and (abs(pending[0]["bbox"][0] - ch["bbox"][2]) < 0.15 or abs(pending[0]["bbox"][0] - ch["bbox"][0]) < 0.15)):
            units.append({"raw": pending + [ch], "bbox": ch["bbox"], "multi": True})
            pending.clear()
            continue
        flush()
        units.append({"raw": [ch], "bbox": ch["bbox"], "multi": False})
    flush()
    return units


def ligature_votes(units):
    """Vote whether this producer stores ligature text reversed (visual) or logical."""
    rev = log = 0
    for u in units:
        if not u["multi"]:
            continue
        t = "".join(c["c"] for c in u["raw"])
        if len(t) == 2 and "ل" in t and (set(t) - {"ل"}) <= ALEFS:
            if t[0] == "ل":
                log += 1
            else:
                rev += 1
        elif t in ("هلل", "لله"):
            rev += t == "هلل"
            log += t == "لله"
    return rev, log


def _unit_text(u, lig_reversed):
    raw = u["raw"][::-1] if (u["multi"] and lig_reversed) else u["raw"]
    return "".join(c["c"] for c in raw)


def _visual_clusters(chars, size, rtl, lig_reversed, stats):
    """Sort glyph units by x (visual order) and attach each combining mark to the base under it."""
    bases, marks = [], []
    for u in glyph_units(chars, size):
        c = u["raw"][0]["c"]
        if len(u["raw"]) == 1 and (c in BIDI_CONTROLS or c in ("\u200b", "\ufeff")):
            stats["bidi_controls"] += 1
            continue
        stats["bad_chars"] += sum(1 for ch in u["raw"] if is_bad(ch["c"]))
        if u["multi"]:
            stats["ligatures"] += 1
        unit = {"c": _unit_text(u, lig_reversed), "bbox": u["bbox"]}
        (marks if u.get("mark") else bases).append(unit)
    order = sorted(range(len(bases)), key=lambda i: _cx(bases[i]), reverse=rtl)
    clusters = [[bases[i]] for i in order]
    if not clusters:
        return []
    for m in marks:
        mx = _cx(m)

        def dist(cl):
            x0, x1 = cl[0]["bbox"][0], cl[0]["bbox"][2]
            return 0 if x0 - 0.5 <= mx <= x1 + 0.5 else min(abs(mx - x0), abs(mx - x1))
        best = min((cl for cl in clusters if not cl[0]["c"].isspace()), key=dist, default=clusters[0])
        best.append(m)
    return clusters


def build_words(chars, size, rtl, stats, lig_reversed=False):
    clusters = _visual_clusters(chars, size, rtl, lig_reversed, stats)
    groups, cur = [], []
    for cl in clusters:
        base = cl[0]
        if base["c"].isspace():
            if cur:
                groups.append(cur)
            cur = []
            continue
        if cur:
            prev = cur[-1][0]
            pw, cw = prev["bbox"][2] - prev["bbox"][0], base["bbox"][2] - base["bbox"][0]
            gap = max(0.0, max(prev["bbox"][0], base["bbox"][0]) - min(prev["bbox"][2], base["bbox"][2]))
            # zero-width glyphs (shaped Arabic clusters) carry no reliable extent
            if pw > 0.05 * size and cw > 0.05 * size and gap > 0.3 * size:
                groups.append(cur)
                cur = []
        cur.append(cl)
    if cur:
        groups.append(cur)
    words = []
    for g in groups:
        script = script_of("".join(cl[0]["c"] for cl in g))
        # visual order equals logical order only for runs matching the line direction
        if (rtl and script in ("L", "N")) or (not rtl and script == "R"):
            g = g[::-1]
        text = "".join(_decode(c, stats) for cl in g for ch in cl for c in ch["c"])
        allc = [ch for cl in g for ch in cl]
        bbox = [min(c["bbox"][0] for c in allc), min(c["bbox"][1] for c in allc),
                max(c["bbox"][2] for c in allc), max(c["bbox"][3] for c in allc)]
        words.append({"t": text, "s": script_of(text), "bbox": bbox})
    return words


def _reverse_runs(tokens, strong, allowed_inside):
    """Visual→logical: reverse runs of opposite-direction tokens embedded in a line."""
    out, i, n = [], 0, len(tokens)
    while i < n:
        if tokens[i]["s"] == strong:
            j, last = i, i
            while j < n and tokens[j]["s"] in allowed_inside:
                if tokens[j]["s"] in (strong, "N"):
                    last = j
                j += 1
            out.extend(tokens[i:last + 1][::-1])
            i = last + 1
        else:
            out.append(tokens[i])
            i += 1
    return out


def _fix_mirrored(word):
    t = word["t"]
    if len(t) >= 2 and t[0] in MIRROR and t[-1] == MIRROR[t[0]]:
        word["t"] = MIRROR[t[0]] + t[1:-1] + t[0]
    return word


def line_direction(chars):
    r = sum(1 for c in chars if is_arabic(c["c"]))
    l_ = sum(1 for c in chars if is_latin(c["c"]))
    return r >= l_


def order_line(words, rtl):
    """Words arrive in visual order; restore logical order of embedded opposite-direction runs."""
    if rtl:
        return [_fix_mirrored(w) for w in _reverse_runs(words, "L", {"L", "N", "O"})], "rtl"
    return _reverse_runs(words, "R", {"R", "N", "O"}), "ltr"


def _merge_lines(raw_lines):
    """Group MuPDF lines sharing a baseline into one visual line."""
    raw_lines.sort(key=lambda ln: ln["y"])
    merged = []
    for ln in raw_lines:
        if merged and abs(merged[-1]["y"] - ln["y"]) < 0.45 * max(ln["size"], merged[-1]["size"]):
            merged[-1]["chars"].extend(ln["chars"])
            merged[-1]["size"] = max(merged[-1]["size"], ln["size"])
        else:
            merged.append(ln)
    return merged


def order_blocks(blocks, width):
    if not blocks:
        return blocks, False
    mid, tol = width / 2, width * 0.04

    def col(b):
        x0, _, x1, _ = b["bbox"]
        if x1 - x0 > 0.62 * width or (x0 < mid - tol and x1 > mid + tol) or abs((x0 + x1) / 2 - mid) < tol:
            return "full"
        return "right" if x0 >= mid - tol else "left"

    for b in blocks:
        b["col"] = col(b)
    rights = [b for b in blocks if b["col"] == "right"]
    lefts = [b for b in blocks if b["col"] == "left"]
    two_cols = any(r["bbox"][1] < lf["bbox"][3] and lf["bbox"][1] < r["bbox"][3] for r in rights for lf in lefts)
    if not two_cols:
        return sorted(blocks, key=lambda b: (round(b["bbox"][1], 1), -b["bbox"][2])), False
    ordered, band = [], []
    for b in sorted(blocks, key=lambda b: b["bbox"][1]):
        if b["col"] == "full":
            ordered += sorted([x for x in band if x["col"] == "right"], key=lambda x: x["bbox"][1])
            ordered += sorted([x for x in band if x["col"] == "left"], key=lambda x: x["bbox"][1])
            ordered.append(b)
            band = []
        else:
            band.append(b)
    ordered += sorted([x for x in band if x["col"] == "right"], key=lambda x: x["bbox"][1])
    ordered += sorted([x for x in band if x["col"] == "left"], key=lambda x: x["bbox"][1])
    return ordered, True


def _image_coverage(page):
    area = page.rect.width * page.rect.height or 1
    total = 0.0
    try:
        for info in page.get_image_info():
            r = pymupdf.Rect(info["bbox"]) & page.rect
            total += r.width * r.height
    except Exception:
        return 0.0
    return min(1.0, total / area)


def _raw_blocks(raw):
    out = []
    for b in raw.get("blocks", []):
        if b.get("type") != 0:
            continue
        raw_lines = []
        for ln in b.get("lines", []):
            chars, sizes = [], []
            for sp in ln.get("spans", []):
                for ch in sp.get("chars", []):
                    chars.append(ch)
                    sizes.append(sp.get("size", 10))
            if chars:
                raw_lines.append({"y": statistics.median([c["origin"][1] for c in chars]),
                                  "size": statistics.median(sizes), "chars": chars})
        if raw_lines:
            out.append(_merge_lines(raw_lines))
    return out


def extract_page(doc, index, lig_hint=None):
    """lig_hint: document-level guess (True = ligature text stored reversed) used when the page has no votes."""
    page = doc[index]
    width, height = page.rect.width, page.rect.height
    stats = defaultdict(int)
    raw_blocks = _raw_blocks(page.get_text("rawdict", flags=FLAGS))
    rev = log = 0
    for rb in raw_blocks:
        for ml in rb:
            r_, l_ = ligature_votes(glyph_units(ml["chars"], ml["size"]))
            rev, log = rev + r_, log + l_
    lig_reversed = rev > log if (rev or log) else bool(lig_hint)
    stats["lig_votes_reversed"], stats["lig_votes_logical"] = rev, log
    if lig_reversed:
        stats["ligatures_reversed"] = 1
    blocks = []
    for rb in raw_blocks:
        lines = []
        for ml in rb:
            rtl = line_direction(ml["chars"])
            words = build_words(ml["chars"], ml["size"], rtl, stats, lig_reversed)
            if not words:
                continue
            ordered, direction = order_line(words, rtl)
            bb = [min(w["bbox"][0] for w in ordered), min(w["bbox"][1] for w in ordered),
                  max(w["bbox"][2] for w in ordered), max(w["bbox"][3] for w in ordered)]
            lines.append({"words": [w["t"] for w in ordered], "scripts": [w["s"] for w in ordered],
                          "text": " ".join(w["t"] for w in ordered), "bbox": [round(v, 1) for v in bb],
                          "size": round(ml["size"], 2), "dir": direction})
        if not lines:
            continue
        bbox = [min(x["bbox"][0] for x in lines), min(x["bbox"][1] for x in lines),
                max(x["bbox"][2] for x in lines), max(x["bbox"][3] for x in lines)]
        blocks.append({"bbox": bbox, "lines": lines})

    blocks, two_cols = order_blocks(blocks, width)
    for b in blocks:
        b.pop("col", None)
    return {"width": width, "height": height, "blocks": blocks, "two_columns": two_cols,
            "image_coverage": _image_coverage(page), "stats": dict(stats)}


def _furniture_key(text):
    return re.sub(r"[0-9٠-٩۰-۹]+", "#", text).strip()


def detect_furniture(pages):
    """Mark repeated header/footer lines. Exclude only on high confidence."""
    n = len(pages)
    counts = defaultdict(set)
    for p in pages:
        h = p["height"] or 1
        for b in p["blocks"]:
            for ln in b["lines"]:
                zone = "header" if ln["bbox"][3] < 0.1 * h else ("footer" if ln["bbox"][1] > 0.9 * h else None)
                if zone:
                    ln["_zone"] = zone
                    counts[(zone, _furniture_key(ln["text"]))].add(p["page_number"])
    for p in pages:
        for b in p["blocks"]:
            for ln in b["lines"]:
                zone = ln.pop("_zone", None)
                ln["role"] = "body"
                ln["excluded"] = False
                ln["furniture_confidence"] = 0.0
                if not zone:
                    continue
                c = len(counts[(zone, _furniture_key(ln["text"]))])
                key = _furniture_key(ln["text"])
                page_num_only = bool(re.fullmatch(r"[#\s\-–—|/()\[\]صفحة]*#[#\s\-–—|/()\[\]]*", key))
                if n >= 3 and c >= 3 and (c >= 0.4 * n or page_num_only):
                    conf = round(min(1.0, 0.6 + 0.4 * c / n), 2)
                elif c >= 2:
                    conf = round(0.3 + 0.2 * c / max(n, 1), 2)
                else:
                    continue
                ln["role"] = zone
                ln["furniture_confidence"] = conf
                ln["excluded"] = conf >= 0.75


def mark_footnotes(page):
    sizes = [ln["size"] for b in page["blocks"] for ln in b["lines"] if ln["role"] == "body"]
    if len(sizes) < 4:
        return
    med = statistics.median(sizes)
    h = page["height"] or 1
    for b in page["blocks"]:
        for ln in b["lines"]:
            if ln["role"] == "body" and ln["size"] < 0.85 * med and ln["bbox"][1] > 0.6 * h:
                ln["role"] = "footnote"


def assess_page(page):
    """Compute status + confidence; warn rather than silently accept bad text."""
    s = page["stats"]
    issues, conf = [], 1.0
    words = [(w, sc) for b in page["blocks"] for ln in b["lines"] for w, sc in zip(ln["words"], ln["scripts"])]
    chars = sum(len(w) for w, _ in words)
    cov = page["image_coverage"]
    if chars < 15:
        if cov > 0.3:
            return "needs_ocr", 0.0, ["scanned_page"]
        return "empty", 0.0, ["no_text"]
    bad_ratio = s.get("bad_chars", 0) / max(chars, 1)
    if bad_ratio > 0.05:
        return "needs_ocr", 0.1, ["broken_font_encoding"]
    if bad_ratio > 0:
        issues.append("some_unknown_glyphs")
        conf -= min(0.3, bad_ratio * 6)
    ar = [w for w, sc in words if sc == "R"]
    if len(ar) >= 20:
        singles = sum(1 for w in ar if len([c for c in w if is_arabic(c) and not unicodedata.combining(c)]) == 1
                      and w.strip(".,،؛:!؟()«»\"'") not in SINGLE_LETTER_OK)
        frag = singles / len(ar)
        if frag > 0.4:
            return "needs_ocr", 0.15, ["fragmented_arabic_words"]
        if frag > 0.15:
            issues.append("fragmented_arabic_words")
            conf -= 0.35
    if cov > 0.5 and chars < 400:
        issues.append("mixed_image_text")
        conf -= 0.35
    if s.get("reversed_words", 0):
        issues.append("visual_order_fixed")
        conf -= 0.1
    if s.get("presentation_chars", 0):
        issues.append("presentation_forms_decoded")
        conf -= 0.05
    if page.get("two_columns"):
        issues.append("two_columns")
        conf -= 0.1
    conf = round(max(0.0, conf), 2)
    status = "ok" if conf >= 0.75 else "warning"
    if "mixed_image_text" in issues:
        status = "needs_ocr" if conf < 0.5 else "warning"
    return status, conf, issues


def page_text(blocks, include_excluded=False):
    return "\n".join(ln["text"] for b in blocks for ln in b["lines"] if include_excluded or not ln.get("excluded"))


def render_png(pdf_bytes, index, dpi=110):
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        pix = doc[index].get_pixmap(dpi=dpi)
        return pix.tobytes("png")


def apply_known_furniture(blocks, known_keys):
    """Exclude OCR header/footer lines that match furniture already confirmed on text pages."""
    lines = [ln for b in blocks for ln in b["lines"]]
    n = len(lines)
    if not n or not known_keys:
        return
    for i, ln in enumerate(lines):
        if (i < 2 or i >= n - 2) and _furniture_key(ln["text"]) in known_keys:
            ln["role"] = "header" if i < 2 else "footer"
            ln["furniture_confidence"] = 0.8
            ln["excluded"] = True
