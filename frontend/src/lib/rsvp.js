export const MODES = [
  { id: "word", label: "كلمة", size: 1 },
  { id: "words3", label: "3 كلمات", size: 3 },
  { id: "words5", label: "5 كلمات", size: 5 },
  { id: "line", label: "سطر", lines: 1 },
  { id: "lines2", label: "سطران", lines: 2 },
];

const SENTENCE_END = ".!?؟…۔";
const CLAUSE_END = "،,؛;:";
const UNREADABLE = ["needs_ocr", "ocr_failed"];

export const MARKER_TEXT = {
  needs_ocr: "تحتاج OCR — لم يُستخرج نص موثوق",
  ocr_failed: "فشل OCR — لا يوجد نص",
};

const lastChar = (t) => t.replace(/[»"')\]]+$/u, "").slice(-1);

export const isSentenceEnd = (t) => SENTENCE_END.includes(lastChar(t));

// Flatten pages into a word stream; unreadable pages become explicit warning markers.
export function buildStream(pages) {
  const words = [];
  const pageStart = {};
  let lineId = 0;
  for (const pg of pages) {
    pageStart[pg.page_number] = words.length;
    if (!pg.lines.length) {
      if (UNREADABLE.includes(pg.status)) {
        words.push({ t: `صفحة ${pg.page_number}: ${MARKER_TEXT[pg.status]}`, p: pg.page_number, l: lineId++, m: true });
      }
      continue;
    }
    for (const ln of pg.lines) {
      for (const w of ln.w) words.push({ t: w, p: pg.page_number, l: lineId, r: ln.r });
      lineId++;
    }
  }
  return { words, pageStart };
}

// Groups never cross pages or warning markers; word groups also break at sentence ends.
export function buildGroups(words, modeId) {
  const mode = MODES.find((m) => m.id === modeId) || MODES[0];
  const groups = [];
  const groupOf = new Int32Array(words.length);
  const push = (s, e) => {
    groups.push([s, e]);
    for (let i = s; i <= e; i++) groupOf[i] = groups.length - 1;
  };
  let s = 0;
  let linesIn = 1;
  for (let i = 0; i < words.length; i++) {
    const w = words[i];
    const next = words[i + 1];
    const hardBreak = !next || w.m || next.m || next.p !== w.p;
    if (mode.size) {
      if (hardBreak || i - s + 1 >= mode.size || isSentenceEnd(w.t)) {
        push(s, i);
        s = i + 1;
      }
    } else if (hardBreak || next.l !== w.l) {
      if (hardBreak || linesIn >= mode.lines) {
        push(s, i);
        s = i + 1;
        linesIn = 1;
      } else {
        linesIn++;
      }
    }
  }
  return { groups, groupOf };
}

// Each word keeps its own duration, with extra pauses after punctuation.
export function wordDuration(t, wpm, punctuationPause) {
  const base = 60000 / wpm;
  if (!punctuationPause) return base;
  let f = 1;
  const c = lastChar(t);
  if (SENTENCE_END.includes(c)) f += 1.0;
  else if (CLAUSE_END.includes(c)) f += 0.5;
  if ([...t].length > 8) f += 0.2;
  return base * f;
}

export const STATUS_META = {
  ok: { label: "سليمة", cls: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" },
  warning: { label: "ثقة منخفضة", cls: "bg-amber-500/10 text-amber-400 border-amber-500/20" },
  needs_ocr: { label: "تحتاج OCR", cls: "bg-orange-500/10 text-orange-400 border-orange-500/30" },
  empty: { label: "فارغة", cls: "bg-neutral-500/10 text-neutral-400 border-neutral-600/30" },
  ocr_done: { label: "OCR غير مُراجَع", cls: "bg-sky-500/10 text-sky-400 border-sky-500/20" },
  ocr_failed: { label: "فشل OCR", cls: "bg-red-500/10 text-red-400 border-red-500/20" },
  processing: { label: "قيد المعالجة", cls: "bg-blue-500/10 text-blue-400 border-blue-500/20" },
  ready: { label: "جاهز", cls: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" },
  ready_with_warnings: { label: "جاهز مع تحذيرات", cls: "bg-amber-500/10 text-amber-400 border-amber-500/20" },
  extraction_failed: { label: "فشل الاستخراج", cls: "bg-red-500/10 text-red-400 border-red-500/20" },
  failed: { label: "فشل", cls: "bg-red-500/10 text-red-400 border-red-500/20" },
};

export const ISSUE_LABELS = {
  scanned_page: "صفحة مصوّرة بلا طبقة نص",
  no_text: "لا يوجد نص",
  broken_font_encoding: "ترميز خط تالف — النص المستخرج غير موثوق",
  some_unknown_glyphs: "بعض الحروف غير معروفة",
  fragmented_arabic_words: "كلمات عربية مفككة",
  mixed_image_text: "صفحة مختلطة (صور + نص)",
  visual_order_fixed: "تم تصحيح ترتيب بصري معكوس",
  presentation_forms_decoded: "تم فك أشكال العرض العربية",
  two_columns: "عمودان — راجع الترتيب",
  extraction_error: "خطأ أثناء الاستخراج",
  ocr_unverified: "نص OCR غير مُراجَع",
  ocr_unreadable_words: "بعض الكلمات بثقة منخفضة",
  ocr_no_text: "OCR لم يجد نصاً",
  ocr_error: "خطأ في محرك OCR",
  ocr_low_confidence: "ثقة OCR منخفضة — قارن بالأصل",
};
