import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { toast } from "sonner";
import { api, API, formatApiError } from "@/lib/api";
import { buildGroups, buildStream } from "@/lib/rsvp";
import { useRsvp } from "@/hooks/useRsvp";
import { FullScreenLoader } from "@/components/FullScreenLoader";
import { RsvpStage } from "@/components/reader/RsvpStage";
import { ControlBar } from "@/components/reader/ControlBar";
import { PagePanel } from "@/components/reader/PagePanel";
import { PageWarning } from "@/components/reader/PageWarning";
import { useReaderKeys } from "@/hooks/useReaderKeys";
import { useBookmarks } from "@/hooks/useBookmarks";
import { ReaderIndex } from "@/components/reader/ReaderIndex";

function ReaderView({ doc, pages, init }) {
  const { words, pageStart } = useMemo(() => buildStream(pages), [pages]);
  const [modeId, setModeId] = useState(init.mode);
  const [wpm, setWpm] = useState(init.wpm);
  const [punct, setPunct] = useState(init.punct);
  const [panel, setPanel] = useState(false);
  const [indexOpen, setIndexOpen] = useState(false);
  const bm = useBookmarks(doc.document_id);
  const { groups, groupOf } = useMemo(() => buildGroups(words, modeId), [words, modeId]);
  const onMarker = useCallback(() => toast.warning("توقف القارئ: صفحة بلا نص موثوق"), []);
  const r = useRsvp({ words, groups, groupOf, wpm, punct, initialIdx: Math.min(init.idx, Math.max(0, words.length - 1)), onMarker });
  const cur = words[r.idx];
  const pageNumber = cur?.p || 1;
  const pageMeta = pages.find((p) => p.page_number === pageNumber);
  const pageNums = pages.map((p) => p.page_number);

  const payload = useRef();
  payload.current = { word_index: r.idx, total_words: words.length, page_number: pageNumber, wpm, mode: modeId };
  const save = useCallback(async (manual) => {
    try {
      await api.put(`/documents/${doc.document_id}/progress`, payload.current);
      if (manual) toast.success(`تم حفظ الموضع — صفحة ${payload.current.page_number}`);
    } catch (e) {
      if (manual) toast.error(formatApiError(e));
    }
  }, [doc.document_id]);

  useEffect(() => {
    const t = setTimeout(() => save(false), r.playing ? 4000 : 800);
    return () => clearTimeout(t);
  }, [r.idx, r.playing, wpm, modeId, save]);

  useEffect(() => {
    const t = setTimeout(() => api.put("/settings", { wpm, mode: modeId, punctuation_pause: punct }).catch(() => {}), 1200);
    return () => clearTimeout(t);
  }, [wpm, modeId, punct]);

  useEffect(() => () => {
    fetch(`${API}/documents/${doc.document_id}/progress`, {
      method: "PUT", credentials: "include", keepalive: true,
      headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload.current),
    }).catch(() => {});
  }, [doc.document_id]);

  const goPage = useCallback((delta) => {
    const i = pageNums.indexOf(pageNumber) + delta;
    if (i < 0 || i >= pageNums.length) return;
    const target = pageStart[pageNums[i]];
    if (target === undefined || target >= words.length) return;
    r.seek(target);
  }, [pageNums, pageNumber, pageStart, words.length, r]);

  const addBookmark = useCallback(() => {
    const w = words[r.idx];
    if (!w) return;
    const snippet = words.slice(r.idx, r.idx + 10).map((x) => x.t).join(" ");
    bm.add(r.idx, w.p, snippet);
  }, [words, r.idx, bm]);

  const jumpTo = useCallback((i) => { r.setPlaying(false); r.seek(i); setIndexOpen(false); }, [r]);
  const jumpPage = useCallback((p) => {
    const t = pageStart[p];
    if (t === undefined || t >= words.length) return toast.warning("لا يوجد نص في هذه الصفحة");
    jumpTo(t);
  }, [pageStart, words.length, jumpTo]);

  useReaderKeys({ r, setWpm, goPage, addBookmark });

  if (!words.length) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4 text-center p-8" data-testid="reader-empty">
        <p className="text-xl font-bold text-orange-300">لا يوجد نص موثوق للقراءة في هذا الملف</p>
        <Link to={`/documents/${doc.document_id}`} className="underline text-neutral-400">افتح صفحة الملف لتشغيل OCR</Link>
      </div>
    );
  }

  const remainMin = Math.max(0, Math.round((words.length - r.idx) / wpm));
  const info = `صفحة ${pageNumber} من ${doc.page_count} · كلمة ${r.idx + 1} من ${words.length} · متبقٍ ≈ ${remainMin} دقيقة`;

  return (
    <div className="min-h-screen bg-[#0a0a0a] flex flex-col" data-testid="reader-page">
      <header className="px-6 sm:px-10 h-16 flex items-center justify-between border-b border-neutral-900">
        <Link to="/library" className="flex items-center gap-2 text-sm text-neutral-400 hover:text-white transition-colors" data-testid="reader-back-btn">
          <ArrowRight className="h-4 w-4" /> المكتبة
        </Link>
        <h1 className="text-sm opacity-50 truncate max-w-[50%]" data-testid="reader-doc-title">{doc.title}</h1>
        <span className="text-xs font-mono text-neutral-500" data-testid="reader-page-indicator">ص {pageNumber}</span>
      </header>
      <PageWarning page={pageMeta} onCompare={() => setPanel(true)} />
      <main className="flex-1 flex items-center justify-center pb-48 pt-8 select-none">
        <RsvpStage words={words} group={groups[groupOf[r.idx]]} idx={r.idx} modeId={modeId} onShowOriginal={() => setPanel(true)} />
      </main>
      <ControlBar r={r} wpm={wpm} setWpm={setWpm} modeId={modeId} setModeId={setModeId} punct={punct} setPunct={setPunct}
        onSave={() => save(true)} onToggleOriginal={() => setPanel((o) => !o)} onPrevPage={() => goPage(-1)} onNextPage={() => goPage(1)}
        onBookmark={addBookmark} onOpenIndex={() => setIndexOpen(true)}
        marks={bm.bookmarks.map((b) => ({ id: b.bookmark_id, pct: (b.word_index / words.length) * 100 }))}
        progressPct={((r.idx + 1) / words.length) * 100} info={info} />
      <ReaderIndex open={indexOpen} onOpenChange={setIndexOpen} bookmarks={bm.bookmarks} pages={pages} pageStart={pageStart}
        toc={bm.toc} current={pageNumber} onJump={jumpTo} onJumpPage={jumpPage} onDeleteBookmark={bm.remove} />
      <PagePanel open={panel} docId={doc.document_id} pageNumber={pageNumber} onClose={() => setPanel(false)} />
    </div>
  );
}

export default function Reader() {
  const { id } = useParams();
  const [state, setState] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api.get(`/documents/${id}`), api.get(`/documents/${id}/content`),
      api.get(`/documents/${id}/progress`), api.get("/settings"),
    ]).then(([d, c, p, s]) => {
      const prog = p.data, set = s.data;
      setState({
        doc: d.data, pages: c.data.pages,
        init: { idx: prog.word_index || 0, wpm: prog.wpm || set.wpm, mode: prog.mode || set.mode, punct: set.punctuation_pause ?? true },
      });
    }).catch((e) => setError(formatApiError(e)));
  }, [id]);

  if (error) return <div className="p-10 text-red-400" data-testid="reader-error">{error}</div>;
  if (!state) return <FullScreenLoader label="تحميل النص…" />;
  return <ReaderView {...state} />;
}
