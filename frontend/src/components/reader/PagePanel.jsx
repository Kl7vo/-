import { memo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X } from "lucide-react";
import { PageCompare } from "@/components/PageCompare";

export const PagePanel = memo(function PagePanel({ open, docId, pageNumber, onClose }) {
  return (
    <AnimatePresence>
      {open && (
        <motion.aside
          initial={{ x: "-100%" }} animate={{ x: 0 }} exit={{ x: "-100%" }} transition={{ duration: 0.25, ease: "easeOut" }}
          className="fixed top-0 left-0 bottom-0 z-40 w-full sm:w-[46vw] max-w-[760px] bg-[#121212] border-e border-neutral-800 overflow-y-auto"
          data-testid="original-page-panel"
        >
          <div className="sticky top-0 bg-[#121212]/95 backdrop-blur-xl border-b border-neutral-800 px-6 h-14 flex items-center justify-between z-10">
            <span className="font-bold">الصفحة الأصلية · {pageNumber}</span>
            <button onClick={onClose} className="p-2 hover:bg-white/10 transition-colors rounded-sm" data-testid="close-original-panel-btn" aria-label="إغلاق">
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="p-6">
            <PageCompare docId={docId} pageNumber={pageNumber} />
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
});
