import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { AppHeader } from "@/components/AppHeader";
import { UploadDropzone } from "@/components/UploadDropzone";
import { DocumentCard } from "@/components/DocumentCard";
import { api, formatApiError } from "@/lib/api";

export default function Library() {
  const [docs, setDocs] = useState(null);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/documents");
      setDocs(data);
    } catch (e) {
      toast.error(formatApiError(e));
      setDocs([]);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!docs?.some((d) => d.status === "processing")) return;
    const t = setInterval(load, 2500);
    return () => clearInterval(t);
  }, [docs, load]);

  const onDelete = async (doc) => {
    try {
      await api.delete(`/documents/${doc.document_id}`);
      toast.success("تم حذف الملف");
      setDocs((d) => d.filter((x) => x.document_id !== doc.document_id));
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };

  return (
    <div className="min-h-screen grain">
      <AppHeader />
      <main className="relative z-10 max-w-7xl mx-auto px-6 sm:px-10 py-12 sm:py-16">
        <div className="mb-12 fade-up">
          <p className="text-xs font-bold tracking-[0.2em] text-[#e11d48] mb-3">المكتبة</p>
          <h1 className="text-4xl sm:text-5xl font-bold tracking-tight">ملفاتك</h1>
          <p className="text-neutral-400 mt-4 max-w-xl text-sm sm:text-base">
            كل ملف يُعالج صفحةً صفحة. الصفحات التي لا نثق بنصها تُعلَّم بوضوح ويمكن إرسالها إلى OCR أو مقارنتها بالأصل.
          </p>
        </div>
        <UploadDropzone />
        <section className="mt-14" data-testid="documents-grid">
          {docs === null && <p className="text-neutral-500 text-sm">جارٍ التحميل…</p>}
          {docs?.length === 0 && (
            <p className="text-neutral-500 text-sm border border-neutral-800 p-10 text-center" data-testid="library-empty">
              لا توجد ملفات بعد. ارفع أول ملف PDF للبدء.
            </p>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {docs?.map((d, i) => <DocumentCard key={d.document_id} doc={d} index={i} onDelete={onDelete} />)}
          </div>
        </section>
      </main>
    </div>
  );
}
