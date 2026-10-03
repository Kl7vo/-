import { BookmarkPlus, ChevronsLeft, ChevronsRight, Eye, ListTree, Pause, Play, Save, SkipBack, SkipForward } from "lucide-react";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { MODES } from "@/lib/rsvp";

const IconBtn = ({ onClick, label, testId, children }) => (
  <button onClick={onClick} aria-label={label} title={label} data-testid={testId}
    className="h-10 w-10 flex items-center justify-center text-neutral-300 hover:text-white hover:bg-white/10 transition-colors rounded-sm">
    {children}
  </button>
);

const WpmControl = ({ wpm, setWpm }) => (
  <div className="flex items-center gap-3 min-w-[220px] flex-1">
    <Slider dir="rtl" min={100} max={5000} step={25} value={[wpm]} onValueChange={([v]) => setWpm(v)}
      className="flex-1" data-testid="wpm-slider" />
    <input type="number" min={100} max={5000} step={25} value={wpm} dir="ltr" data-testid="wpm-input"
      onChange={(e) => setWpm(Math.max(100, Math.min(5000, Number(e.target.value) || 100)))}
      className="w-20 h-9 bg-[#171717] border border-neutral-700 text-center font-mono text-sm rounded-sm focus:outline-none focus:ring-2 focus:ring-[#e11d48]" />
    <span className="text-xs text-neutral-500 whitespace-nowrap">كلمة/د</span>
  </div>
);

export const ControlBar = ({ r, wpm, setWpm, modeId, setModeId, punct, setPunct, onSave, onToggleOriginal, onPrevPage, onNextPage, onBookmark, onOpenIndex, marks, progressPct, info }) => (
  <div className="fixed bottom-0 inset-x-0 z-30 backdrop-blur-xl bg-black/60 border-t border-white/10" data-testid="reader-control-bar">
    <div className="relative h-1 bg-neutral-800">
      <div className="h-1 bg-[#e11d48]" style={{ width: `${progressPct}%` }} data-testid="reader-progress-bar" />
      {marks.map((m) => (
        <span key={m.id} className="absolute -top-1 h-3 w-0.5 bg-amber-400" style={{ insetInlineStart: `${m.pct}%` }} data-testid="progress-bookmark-tick" />
      ))}
    </div>
    <div className="max-w-7xl mx-auto px-4 sm:px-8 py-4 flex flex-wrap items-center gap-x-6 gap-y-3">
      <div className="flex items-center gap-1">
        <IconBtn onClick={onPrevPage} label="الصفحة السابقة" testId="prev-page-btn"><ChevronsRight className="h-5 w-5" /></IconBtn>
        <IconBtn onClick={r.back} label="رجوع" testId="rewind-btn"><SkipBack className="h-5 w-5 rotate-180" /></IconBtn>
        <button onClick={r.toggle} data-testid="play-pause-btn" aria-label={r.playing ? "إيقاف" : "تشغيل"}
          className="h-14 w-14 rounded-full bg-[#e11d48] hover:bg-[#be123c] flex items-center justify-center mx-2 transition-colors focus:outline-none focus:ring-2 focus:ring-white/40">
          {r.playing ? <Pause className="h-6 w-6" /> : <Play className="h-6 w-6 rotate-180" />}
        </button>
        <IconBtn onClick={r.forward} label="تقديم" testId="forward-btn"><SkipForward className="h-5 w-5 rotate-180" /></IconBtn>
        <IconBtn onClick={onNextPage} label="الصفحة التالية" testId="next-page-btn"><ChevronsLeft className="h-5 w-5" /></IconBtn>
      </div>
      <ToggleGroup type="single" value={modeId} onValueChange={(v) => v && setModeId(v)} dir="rtl" className="gap-0 border border-neutral-700 rounded-sm" data-testid="mode-toggle">
        {MODES.map((m) => (
          <ToggleGroupItem key={m.id} value={m.id} data-testid={`mode-${m.id}`}
            className="rounded-none h-9 px-3 text-xs data-[state=on]:bg-white data-[state=on]:text-black">{m.label}</ToggleGroupItem>
        ))}
      </ToggleGroup>
      <WpmControl wpm={wpm} setWpm={setWpm} />
      <label className="flex items-center gap-2 text-xs text-neutral-400">
        <Switch checked={punct} onCheckedChange={setPunct} data-testid="punctuation-pause-switch" /> وقفات الترقيم
      </label>
      <div className="flex items-center gap-1 ms-auto">
        <IconBtn onClick={onBookmark} label="أضف علامة (B)" testId="add-bookmark-btn"><BookmarkPlus className="h-5 w-5" /></IconBtn>
        <IconBtn onClick={onOpenIndex} label="الفهرس والعلامات" testId="open-index-btn"><ListTree className="h-5 w-5" /></IconBtn>
        <IconBtn onClick={onSave} label="حفظ الموضع" testId="save-position-btn"><Save className="h-5 w-5" /></IconBtn>
        <IconBtn onClick={onToggleOriginal} label="الصفحة الأصلية" testId="toggle-original-btn"><Eye className="h-5 w-5" /></IconBtn>
      </div>
      <p className="w-full text-xs text-neutral-500 font-mono" data-testid="reader-position-info">{info}</p>
    </div>
  </div>
);
