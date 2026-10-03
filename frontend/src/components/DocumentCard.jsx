import { Link } from "react-router-dom";
import { BookOpen, FileText, ListChecks, Trash2 } from "lucide-react";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { StatusBadge } from "@/components/StatusBadge";

const DeleteButton = ({ doc, onDelete }) => (
  <AlertDialog>
    <AlertDialogTrigger asChild>
      <button className="p-2 text-neutral-500 hover:text-red-400 transition-colors" data-testid={`delete-doc-btn-${doc.document_id}`} aria-label="حذف">
        <Trash2 className="h-4 w-4" />
      </button>
    </AlertDialogTrigger>
    <AlertDialogContent dir="rtl" className="bg-[#171717] border-neutral-800 rounded-sm">
      <AlertDialogHeader className="text-right sm:text-right">
        <AlertDialogTitle>حذف «{doc.title}»؟</AlertDialogTitle>
        <AlertDialogDescription>سيُحذف النص المستخرج وموضع القراءة نهائياً من مكتبتك.</AlertDialogDescription>
      </AlertDialogHeader>
      <AlertDialogFooter className="gap-2 sm:gap-2 sm:justify-start">
        <AlertDialogAction onClick={() => onDelete(doc)} className="bg-red-600 hover:bg-red-700 rounded-sm" data-testid="confirm-delete-btn">حذف</AlertDialogAction>
        <AlertDialogCancel className="rounded-sm" data-testid="cancel-delete-btn">إلغاء</AlertDialogCancel>
      </AlertDialogFooter>
    </AlertDialogContent>
  </AlertDialog>
);

export const DocumentCard = ({ doc, onDelete, index }) => {
  const pct = doc.progress?.total_words ? Math.round((doc.progress.word_index / doc.progress.total_words) * 100) : 0;
  const readable = !["processing", "failed", "extraction_failed"].includes(doc.status);
  const st = doc.page_stats || {};
  const flagged = (st.needs_ocr || 0) + (st.warning || 0) + (st.ocr_failed || 0);
  return (
    <article data-testid={`doc-card-${doc.document_id}`} style={{ animationDelay: `${index * 50}ms` }}
      className="fade-up flex flex-col bg-[#171717] border border-neutral-800 hover:border-neutral-600 hover:-translate-y-1 transition-[transform,border-color] duration-200 rounded-sm">
      <div className="p-6 flex-1">
        <div className="flex items-start justify-between gap-3 mb-6">
          <FileText className="h-5 w-5 text-neutral-500 shrink-0 mt-1" />
          <StatusBadge status={doc.status} testId={`doc-status-${doc.document_id}`} />
        </div>
        <h3 className="font-bold text-lg leading-snug line-clamp-2" data-testid={`doc-title-${doc.document_id}`}>{doc.title}</h3>
        <p className="text-xs text-neutral-500 mt-3 font-mono" dir="ltr">
          {doc.page_count} pp · {(doc.size / 1048576).toFixed(1)} MB
        </p>
        {flagged > 0 && <p className="text-xs text-amber-400 mt-2">{flagged} صفحة تحتاج مراجعة أو OCR</p>}
      </div>
      <div className="h-1 bg-neutral-800"><div className="h-1 bg-[#e11d48]" style={{ width: `${pct}%` }} /></div>
      <div className="flex items-center justify-between px-4 py-3 border-t border-neutral-800">
        <div className="flex items-center gap-1">
          {readable && (
            <Link to={`/read/${doc.document_id}`} data-testid={`read-doc-btn-${doc.document_id}`}
              className="flex items-center gap-2 px-3 py-1.5 text-sm bg-[#e11d48] hover:bg-[#be123c] transition-colors rounded-sm">
              <BookOpen className="h-4 w-4" /> {pct > 0 ? `متابعة ${pct}%` : "اقرأ"}
            </Link>
          )}
          <Link to={`/documents/${doc.document_id}`} data-testid={`status-doc-btn-${doc.document_id}`}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-neutral-300 hover:bg-white/5 transition-colors rounded-sm">
            <ListChecks className="h-4 w-4" /> الصفحات
          </Link>
        </div>
        <DeleteButton doc={doc} onDelete={onDelete} />
      </div>
    </article>
  );
};
