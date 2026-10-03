import { AlertTriangle } from "lucide-react";
import { ISSUE_LABELS } from "@/lib/rsvp";

const TONE = {
  warning: "border-amber-500/30 bg-amber-500/10 text-amber-200",
  ocr_done: "border-sky-500/30 bg-sky-500/10 text-sky-200",
  needs_ocr: "border-orange-500/40 bg-orange-500/10 text-orange-200",
  ocr_failed: "border-red-500/40 bg-red-500/10 text-red-200",
};

const TITLE = {
  warning: "ثقة منخفضة في نص هذه الصفحة",
  ocr_done: "نص هذه الصفحة من OCR ولم يُراجَع",
  needs_ocr: "هذه الصفحة تحتاج OCR",
  ocr_failed: "فشل OCR لهذه الصفحة",
};

export const PageWarning = ({ page, onCompare }) => {
  if (!page || !TONE[page.status]) return null;
  const issues = (page.issues || []).map((i) => ISSUE_LABELS[i] || i).join(" · ");
  return (
    <div className={`mx-auto max-w-3xl mt-4 border px-4 py-3 flex items-center gap-3 text-sm rounded-sm ${TONE[page.status]}`} data-testid="page-warning-banner">
      <AlertTriangle className="h-4 w-4 shrink-0" />
      <p className="flex-1"><strong>{TITLE[page.status]}</strong>{issues && <span className="opacity-80"> — {issues}</span>}</p>
      <button onClick={onCompare} className="underline underline-offset-4 whitespace-nowrap" data-testid="warning-compare-btn">قارن بالأصل</button>
    </div>
  );
};
