import { Eye, ScanText } from "lucide-react";
import { StatusBadge } from "@/components/StatusBadge";
import { ISSUE_LABELS } from "@/lib/rsvp";

const OCR_ALLOWED = ["needs_ocr", "ocr_failed", "warning", "empty"];

export const PagesTable = ({ pages, running, onPreview, onOcr }) => (
  <div className="border border-neutral-800 rounded-sm overflow-x-auto" data-testid="pages-table">
    <table className="w-full text-sm">
      <thead className="bg-[#121212] text-neutral-500 text-xs">
        <tr>
          <th className="text-start font-medium p-3">الصفحة</th>
          <th className="text-start font-medium p-3">الحالة</th>
          <th className="text-start font-medium p-3">الثقة</th>
          <th className="text-start font-medium p-3">الكلمات</th>
          <th className="text-start font-medium p-3">ملاحظات</th>
          <th className="p-3" />
        </tr>
      </thead>
      <tbody>
        {pages.map((p) => (
          <tr key={p.page_number} className="border-t border-neutral-800 hover:bg-white/[0.02] transition-colors" data-testid={`page-row-${p.page_number}`}>
            <td className="p-3 font-mono">{p.page_number}</td>
            <td className="p-3"><StatusBadge status={p.status} testId={`page-status-${p.page_number}`} /></td>
            <td className="p-3 font-mono text-neutral-400">{Math.round((p.confidence || 0) * 100)}%</td>
            <td className="p-3 font-mono text-neutral-400">
              {p.word_count}
              {p.excluded_lines > 0 && <span className="text-neutral-600 text-xs ms-2 font-sans">(−{p.excluded_lines} سطر تذييل)</span>}
            </td>
            <td className="p-3 text-xs text-neutral-400 max-w-xs">{(p.issues || []).map((i) => ISSUE_LABELS[i] || i).join(" · ")}</td>
            <td className="p-3">
              <div className="flex items-center gap-1 justify-end">
                <button onClick={() => onPreview(p.page_number)} data-testid={`preview-page-btn-${p.page_number}`}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-neutral-300 hover:bg-white/5 transition-colors rounded-sm">
                  <Eye className="h-3.5 w-3.5" /> مقارنة
                </button>
                {OCR_ALLOWED.includes(p.status) && (
                  <button onClick={() => onOcr(p.page_number)} disabled={running} data-testid={`ocr-page-btn-${p.page_number}`}
                    className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-amber-300 hover:bg-amber-500/10 disabled:opacity-40 transition-colors rounded-sm">
                    <ScanText className="h-3.5 w-3.5" /> OCR
                  </button>
                )}
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);
