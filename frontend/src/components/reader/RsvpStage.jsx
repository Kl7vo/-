import { memo } from "react";
import { AlertTriangle, Eye } from "lucide-react";

const Marker = ({ word, onShowOriginal }) => (
  <div className="max-w-xl text-center border border-orange-500/40 bg-orange-500/10 p-8 rounded-sm" data-testid="rsvp-marker">
    <AlertTriangle className="h-8 w-8 text-orange-400 mx-auto mb-4" />
    <p className="text-xl font-bold text-orange-200">{word.t}</p>
    <p className="text-sm text-neutral-400 mt-3">لن نعرض نصاً غير موثوق. يمكنك مقارنة الصفحة الأصلية أو تشغيل OCR من صفحة الملف.</p>
    <button onClick={onShowOriginal} data-testid="marker-show-original-btn"
      className="mt-6 inline-flex items-center gap-2 px-4 py-2 border border-neutral-600 hover:bg-white/5 transition-colors text-sm rounded-sm">
      <Eye className="h-4 w-4" /> عرض الصفحة الأصلية
    </button>
  </div>
);

const Lines = ({ words, start, idx, big }) => {
  const lines = [];
  words.forEach((w, k) => {
    const last = lines[lines.length - 1];
    if (!last || last.l !== w.l) lines.push({ l: w.l, items: [] });
    lines[lines.length - 1].items.push({ w, i: start + k });
  });
  return (
    <div className={`font-reader font-bold text-center leading-[1.6] ${big}`} dir="rtl">
      {lines.map((ln) => (
        <p key={ln.l} className="rsvp-word">
          {ln.items.map(({ w, i }, k) => (
            <span key={i} data-testid={i === idx ? "rsvp-current-word" : undefined}
              className={i === idx ? "text-white" : i < idx ? "text-neutral-500" : "text-neutral-600"}>
              {w.t}{k < ln.items.length - 1 ? " " : ""}
            </span>
          ))}
        </p>
      ))}
    </div>
  );
};

export const RsvpStage = memo(function RsvpStage({ words, group, idx, modeId, onShowOriginal }) {
  if (!group) return null;
  const [s, e] = group;
  const slice = words.slice(s, e + 1);
  if (slice[0]?.m) return <Marker word={slice[0]} onShowOriginal={onShowOriginal} />;
  const footnote = slice[0]?.r === "footnote";
  if (modeId === "word") {
    return (
      <div className="relative flex flex-col items-center" data-testid="rsvp-stage">
        <span className="h-4 w-px bg-[#e11d48] mb-6" />
        <p data-testid="rsvp-current-word" dir="rtl"
          className="rsvp-word font-reader font-black text-white text-6xl md:text-7xl lg:text-[100px] leading-none tracking-tight whitespace-nowrap">
          {words[idx].t}
        </p>
        <span className="h-4 w-px bg-[#e11d48] mt-6" />
        {footnote && <span className="mt-6 text-xs text-neutral-500 border border-neutral-700 px-2 py-0.5">حاشية</span>}
      </div>
    );
  }
  const big = modeId.startsWith("words") ? "text-4xl md:text-5xl lg:text-6xl" : "text-2xl md:text-3xl lg:text-4xl";
  return (
    <div className="flex flex-col items-center max-w-5xl px-6" data-testid="rsvp-stage">
      {footnote && <span className="mb-6 text-xs text-neutral-500 border border-neutral-700 px-2 py-0.5">حاشية</span>}
      <Lines words={slice} start={s} idx={idx} big={big} />
    </div>
  );
});
