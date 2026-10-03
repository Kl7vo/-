import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FileUp, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Progress } from "@/components/ui/progress";
import { api, formatApiError } from "@/lib/api";

const MAX_MB = 50;

export const UploadDropzone = () => {
  const inputRef = useRef(null);
  const navigate = useNavigate();
  const [drag, setDrag] = useState(false);
  const [pct, setPct] = useState(null);

  const upload = async (file) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) return toast.error("يُسمح بملفات PDF فقط");
    if (file.size > MAX_MB * 1024 * 1024) return toast.error(`الحد الأقصى ${MAX_MB} ميغابايت`);
    const body = new FormData();
    body.append("file", file);
    setPct(0);
    try {
      const { data } = await api.post("/documents", body, {
        onUploadProgress: (e) => e.total && setPct(Math.round((e.loaded / e.total) * 100)),
      });
      toast.success("تم رفع الملف، بدأت المعالجة");
      navigate(`/documents/${data.document_id}`);
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setPct(null);
    }
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDrag(false);
    upload(e.dataTransfer.files?.[0]);
  };

  return (
    <div
      data-testid="upload-dropzone"
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={onDrop}
      onClick={() => pct === null && inputRef.current?.click()}
      className={`group relative cursor-pointer border border-dashed p-10 sm:p-14 transition-colors rounded-sm ${
        drag ? "border-[#e11d48] bg-[#e11d48]/5" : "border-neutral-700 hover:border-neutral-500 bg-[#121212]"}`}
    >
      <input ref={inputRef} type="file" accept="application/pdf,.pdf" className="hidden" data-testid="upload-file-input"
        onChange={(e) => { upload(e.target.files?.[0]); e.target.value = ""; }} />
      <div className="flex flex-col sm:flex-row sm:items-center gap-6">
        <div className="h-14 w-14 flex items-center justify-center border border-neutral-700 group-hover:border-[#e11d48] transition-colors">
          {pct === null ? <FileUp className="h-6 w-6 text-[#e11d48]" /> : <Loader2 className="h-6 w-6 animate-spin text-[#e11d48]" />}
        </div>
        <div className="flex-1">
          <p className="text-lg font-bold">{pct === null ? "ارفع ملف PDF عربياً" : `جارٍ الرفع… ${pct}%`}</p>
          <p className="text-sm text-neutral-500 mt-1">اسحب الملف هنا أو اضغط للاختيار · حتى {MAX_MB} ميغابايت · يُحفظ الملف الأصلي دائماً</p>
          {pct !== null && <Progress value={pct} className="h-1 mt-4 bg-neutral-800" data-testid="upload-progress" />}
        </div>
      </div>
    </div>
  );
};
