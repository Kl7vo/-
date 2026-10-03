import { useEffect, useState } from "react";
import { AlertTriangle, ImageOff, Loader2 } from "lucide-react";
import { api, formatApiError, pageImageUrl } from "@/lib/api";
import { ISSUE_LABELS } from "@/lib/rsvp";
import { StatusBadge } from "@/components/StatusBadge";

const ROLE_LABEL = { header: "رأس صفحة", footer: "تذييل", footnote: "حاشية" };

const ExtractedLines = ({ page, activeWords }) => (
  <div className="space-y-1.5 font-reader text-[15px] leading-loose" data-testid="compare-extracted-text">
    {page.blocks.flatMap((b) => b.lines).map((ln, i) => (
      <p key={i} className={`${ln.excluded ? "line-through text-neutral-600" : "text-neutral-200"}`}>
        {ln.role !== "body" && (
          <span className="ms-0 me-2 text-[10px] font-sans px-1.5 py-0.5 border border-neutral-700 text-neutral-400 no-underline inline-block align-middle">
            {ROLE_LABEL[ln.role]}{ln.excluded ? " · مستبعد" : ""}{ln.furniture_confidence ? ` ${Math.round(ln.furniture_confidence * 100)}%` : ""}
          </span>
        )}
        {ln.words.map((w, j) => (
          <span key={j} className={activeWords?.has(w) ? "text-[#e11d48]" : ""}>{w}{j < ln.words.length - 1 ? " " : ""}</span>
        ))}
      </p>
    ))}
    {!page.blocks.length && <p className="text-neutral-500 text-sm font-sans">لا يوجد نص مستخرج لهذه الصفحة.</p>}
  </div>
);

export const PageCompare = ({ docId, pageNumber, activeWords }) => {
  const [page, setPage] = useState(null);
  const [err, setErr] = useState("");
  const [imgState, setImgState] = useState("loading");

  useEffect(() => {
    setPage(null);
    setErr("");
    setImgState("loading");
    api.get(`/documents/${docId}/pages/${pageNumber}`).then((r) => setPage(r.data)).catch((e) => setErr(formatApiError(e)));
  }, [docId, pageNumber]);

  return (
    <div className="space-y-6" data-testid="page-compare">
      <div className="relative bg-white min-h-[200px] border border-neutral-800">
        {imgState === "loading" && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#121212] text-neutral-400 gap-2 text-sm">
            <Loader2 className="h-4 w-4 animate-spin" /> تحميل الصفحة الأصلية…
          </div>
        )}
        {imgState === "error" && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#121212] text-red-400 gap-2 text-sm">
            <ImageOff className="h-4 w-4" /> تعذّر عرض الصفحة الأصلية
          </div>
        )}
        <img src={pageImageUrl(docId, pageNumber)} alt={`الصفحة ${pageNumber}`} data-testid="original-page-image"
          onLoad={() => setImgState("ok")} onError={() => setImgState("error")} className="w-full h-auto block" />
      </div>
      {err && <p className="text-red-400 text-sm">{err}</p>}
      {page && (
        <div>
          <div className="flex flex-wrap items-center gap-2 mb-4">
            <StatusBadge status={page.status} testId="compare-page-status" />
            <span className="text-xs text-neutral-500 font-mono" dir="ltr" data-testid="compare-page-meta">
              conf {Math.round(page.confidence * 100)}% · {page.source}{page.ocr_engine ? ` · ${page.ocr_engine}` : ""}{page.ocr_fixes ? ` · ${page.ocr_fixes} fixes` : ""}
            </span>
          </div>
          {page.issues?.length > 0 && (
            <ul className="mb-4 space-y-1" data-testid="compare-page-issues">
              {page.issues.map((i) => (
                <li key={i} className="flex items-center gap-2 text-xs text-amber-400">
                  <AlertTriangle className="h-3.5 w-3.5" /> {ISSUE_LABELS[i] || i}
                </li>
              ))}
            </ul>
          )}
          <ExtractedLines page={page} activeWords={activeWords} />
        </div>
      )}
    </div>
  );
};
