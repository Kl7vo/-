import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { BookOpen, Eye, Loader2, RefreshCw, ScanText } from "lucide-react";
import { toast } from "sonner";
import { Progress } from "@/components/ui/progress";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { AppHeader } from "@/components/AppHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { PageCompare } from "@/components/PageCompare";
import { PagesTable } from "@/components/PagesTable";
import { api, formatApiError } from "@/lib/api";

const STAGE = { extract: "استخراج النص", analyze: "تحليل التذييلات والثقة", ocr: "OCR محلي مجاني", done: "اكتملت" };
const OCR_TARGET = ["needs_ocr", "ocr_failed"];

const JobPanel = ({ job }) => {
  if (!job) return null;
  const pct = job.total ? Math.round(((job.progress || 0) / job.total) * 100) : 0;
  const active = ["queued", "running"].includes(job.status);
  return (
    <div className="border border-neutral-800 bg-[#121212] p-6 rounded-sm" data-testid="job-panel">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          {active && <Loader2 className="h-4 w-4 animate-spin text-[#e11d48]" />}
          <span className="font-bold">{job.type === "ocr" ? "مهمة OCR" : "مهمة المعالجة"}</span>
          <span className="text-sm text-neutral-400" data-testid="job-stage">{STAGE[job.stage] || job.status}</span>
        </div>
        <span className="font-mono text-sm text-neutral-400" dir="ltr" data-testid="job-progress-text">{job.progress || 0}/{job.total || 0}</span>
      </div>
      <Progress value={pct} className="h-1 bg-neutral-800" data-testid="job-progress-bar" />
      {job.status === "failed" && <p className="text-red-400 text-sm mt-4" data-testid="job-error">فشلت المهمة: {job.error}</p>}
      {job.status === "done_with_errors" && <p className="text-amber-400 text-sm mt-4">اكتملت مع أخطاء في {job.failures} صفحة.</p>}
    </div>
  );
};

const Stat = ({ label, value, tone, testId }) => (
  <div className="border border-neutral-800 bg-[#171717] p-5 rounded-sm" data-testid={testId}>
    <p className="text-xs text-neutral-500 mb-2">{label}</p>
    <p className={`text-3xl font-bold font-mono ${tone}`}>{value || 0}</p>
  </div>
);

export default function DocumentStatus() {
  const { id } = useParams();
  const [doc, setDoc] = useState(null);
  const [pages, setPages] = useState([]);
  const [preview, setPreview] = useState(null);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get(`/documents/${id}`);
      setDoc(data);
      if (data.status !== "processing") {
        const pagesResponse = await api.get(`/documents/${id}/pages`);
        setPages(pagesResponse.data);
      }
      return data;
    } catch (e) {
      toast.error(formatApiError(e));
      return null;
    }
  }, [id]);

  useEffect(() => {
    let stopped = false;
    let timer;
    const poll = async () => {
      const data = await load();
      const active = data && (data.status === "processing" || ["queued", "running"].includes(data.job?.status));
      if (!stopped && active) timer = setTimeout(poll, 1500);
    };
    poll();
    return () => { stopped = true; clearTimeout(timer); };
  }, [load]);

  const running = doc?.job && ["queued", "running"].includes(doc.job.status);

  const runOcr = async (pageNumbers) => {
    try {
      const { data } = await api.post(`/documents/${id}/ocr`, { pages: pageNumbers || null });
      toast.success(`بدأ OCR لـ ${data.pages.length} صفحة`);
      load();
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };

  const reprocess = async () => {
    try {
      await api.post(`/documents/${id}/reprocess`);
      toast.success("بدأت إعادة المعالجة — تُحفظ نتائج OCR السابقة");
      load();
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };

  if (!doc) return (<div className="min-h-screen"><AppHeader /><p className="p-10 text-neutral-500">جارٍ التحميل…</p></div>);
  const st = doc.page_stats || {};
  const ocrCount = pages.filter((p) => OCR_TARGET.includes(p.status)).length;

  return (
    <div className="min-h-screen grain">
      <AppHeader />
      <main className="relative z-10 max-w-7xl mx-auto px-6 sm:px-10 py-12 space-y-10">
        <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-6 fade-up">
          <div>
            <Link to="/library" className="text-sm text-neutral-500 hover:text-white transition-colors" data-testid="back-to-library-link">← المكتبة</Link>
            <h1 className="text-3xl sm:text-4xl font-bold mt-4 tracking-tight" data-testid="document-title">{doc.title}</h1>
            <div className="flex items-center gap-3 mt-4">
              <StatusBadge status={doc.status} testId="document-status-badge" />
              <span className="text-xs text-neutral-500 font-mono" dir="ltr">{doc.page_count} pages · {doc.original_filename}</span>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            {doc.status !== "processing" && (
              <button onClick={reprocess} disabled={running} data-testid="reprocess-btn"
                className="flex items-center gap-2 px-4 h-11 border border-neutral-700 text-neutral-300 hover:bg-white/5 disabled:opacity-40 transition-colors rounded-sm">
                <RefreshCw className="h-4 w-4" /> إعادة المعالجة
              </button>
            )}
            {ocrCount > 0 && (
              <button onClick={() => runOcr(null)} disabled={running} data-testid="run-ocr-all-btn"
                className="flex items-center gap-2 px-4 h-11 border border-amber-500/40 text-amber-300 hover:bg-amber-500/10 disabled:opacity-40 transition-colors rounded-sm">
                <ScanText className="h-4 w-4" /> تشغيل OCR مجاني لـ {ocrCount} صفحة
              </button>
            )}
            {!["processing", "failed", "extraction_failed"].includes(doc.status) && (
              <Link to={`/read/${id}`} data-testid="start-reading-btn"
                className="flex items-center gap-2 px-5 h-11 bg-[#e11d48] hover:bg-[#be123c] transition-colors rounded-sm">
                <BookOpen className="h-4 w-4" /> ابدأ القراءة
              </Link>
            )}
          </div>
        </div>
        <JobPanel job={doc.job} />
        {doc.status !== "processing" && (doc.extractor_version || 1) < 2 && (
          <div className="border border-sky-500/30 bg-sky-500/10 text-sky-200 p-5 text-sm rounded-sm" data-testid="extractor-update-alert">
            تحسّن محرك الاستخراج (إصلاح ترتيب الحروف المركّبة مثل «لا» و«في» ولفظ الجلالة). اضغط «إعادة المعالجة» لتطبيقه على هذا الملف.
          </div>
        )}
        {doc.status === "extraction_failed" && (
          <div className="border border-red-500/40 bg-red-500/10 text-red-300 p-5 text-sm rounded-sm" data-testid="extraction-failed-alert">
            لم نتمكن من استخراج نص موثوق من أي صفحة. يبدو أن الملف مصوّر أو بترميز خط تالف — شغّل OCR بدلاً من عرض نص خاطئ.
          </div>
        )}
        {doc.status !== "processing" && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <Stat label="سليمة" value={st.ok} tone="text-emerald-400" testId="stat-ok" />
              <Stat label="ثقة منخفضة" value={st.warning} tone="text-amber-400" testId="stat-warning" />
              <Stat label="تحتاج OCR" value={(st.needs_ocr || 0) + (st.ocr_failed || 0)} tone="text-orange-400" testId="stat-needs-ocr" />
              <Stat label="OCR مكتمل" value={st.ocr_done} tone="text-sky-400" testId="stat-ocr-done" />
              <Stat label="فارغة" value={st.empty} tone="text-neutral-400" testId="stat-empty" />
            </div>
            <PagesTable pages={pages} running={running} onPreview={setPreview} onOcr={(n) => runOcr([n])} />
          </>
        )}
      </main>
      <Dialog open={!!preview} onOpenChange={(o) => !o && setPreview(null)}>
        <DialogContent dir="rtl" className="max-w-3xl max-h-[90vh] overflow-y-auto bg-[#121212] border-neutral-800 rounded-sm" data-testid="page-preview-dialog">
          <DialogHeader className="text-right sm:text-right">
            <DialogTitle className="flex items-center gap-2"><Eye className="h-4 w-4" /> الصفحة {preview} — الأصل مقابل النص المستخرج</DialogTitle>
            <DialogDescription>الأسطر المشطوبة تذييلات متكررة استُبعدت من القراءة.</DialogDescription>
          </DialogHeader>
          {preview && <PageCompare docId={id} pageNumber={preview} />}
        </DialogContent>
      </Dialog>
    </div>
  );
}
