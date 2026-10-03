import { Bookmark, Trash2 } from "lucide-react";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { StatusBadge } from "@/components/StatusBadge";

const Row = ({ onClick, testId, children, active }) => (
  <button onClick={onClick} data-testid={testId}
    className={`w-full text-start px-3 py-2.5 border-b border-neutral-800/70 hover:bg-white/5 transition-colors flex items-center gap-3 ${active ? "bg-white/5" : ""}`}>
    {children}
  </button>
);

const BookmarksTab = ({ bookmarks, onJump, onDelete }) => (
  <div data-testid="bookmarks-list">
    {!bookmarks.length && <p className="text-sm text-neutral-500 p-4">لا توجد علامات بعد. اضغط زر العلامة أو حرف B أثناء القراءة.</p>}
    {bookmarks.map((b) => (
      <div key={b.bookmark_id} className="flex items-stretch border-b border-neutral-800/70" data-testid={`bookmark-item-${b.bookmark_id}`}>
        <button onClick={() => onJump(b.word_index)} data-testid={`bookmark-jump-${b.bookmark_id}`}
          className="flex-1 text-start px-3 py-3 hover:bg-white/5 transition-colors">
          <span className="flex items-center gap-2 text-xs text-[#e11d48] font-bold"><Bookmark className="h-3.5 w-3.5" /> صفحة {b.page_number}</span>
          <span className="block font-reader text-sm text-neutral-200 mt-1 line-clamp-2">{b.snippet}</span>
        </button>
        <button onClick={() => onDelete(b)} aria-label="حذف العلامة" data-testid={`bookmark-delete-${b.bookmark_id}`}
          className="px-3 text-neutral-500 hover:text-red-400 transition-colors"><Trash2 className="h-4 w-4" /></button>
      </div>
    ))}
  </div>
);

const PagesTab = ({ pages, pageStart, current, onJumpPage }) => (
  <div data-testid="pages-index-list">
    {pages.map((p) => (
      <Row key={p.page_number} onClick={() => onJumpPage(p.page_number)} testId={`index-page-${p.page_number}`} active={p.page_number === current}>
        <span className="font-mono text-xs text-neutral-500 w-8">{p.page_number}</span>
        <span className="flex-1 font-reader text-sm text-neutral-300 truncate">
          {p.lines[0]?.w.slice(0, 8).join(" ") || (pageStart[p.page_number] === undefined ? "—" : "بلا نص")}
        </span>
        {p.status !== "ok" && <StatusBadge status={p.status} />}
      </Row>
    ))}
  </div>
);

const TocTab = ({ toc, current, onJumpPage }) => (
  <div data-testid="toc-list">
    {!toc.length && <p className="text-sm text-neutral-500 p-4">لا يحتوي ملف PDF على فهرس داخلي، ولم تُكتشف عناوين.</p>}
    {toc[0]?.auto && <p className="text-xs text-neutral-500 px-4 pb-2" data-testid="toc-auto-note">عناوين مُكتشفة تلقائياً من حجم الخط — قد تحتاج مراجعة.</p>}
    {toc.map((t, i) => (
      <Row key={i} onClick={() => onJumpPage(t.page)} testId={`toc-item-${i}`} active={t.page === current}>
        <span className="flex-1 text-sm" style={{ paddingInlineStart: `${(t.level - 1) * 14}px` }}>{t.title}</span>
        <span className="font-mono text-xs text-neutral-500">{t.page}</span>
      </Row>
    ))}
  </div>
);

export const ReaderIndex = ({ open, onOpenChange, bookmarks, pages, pageStart, toc, current, onJump, onJumpPage, onDeleteBookmark }) => (
  <Sheet open={open} onOpenChange={onOpenChange}>
    <SheetContent side="right" dir="rtl" className="w-full sm:max-w-md bg-[#121212] border-neutral-800 p-0 flex flex-col" data-testid="reader-index-sheet">
      <SheetHeader className="text-right sm:text-right px-6 pt-6 pb-2 pe-12">
        <SheetTitle>الفهرس</SheetTitle>
        <SheetDescription>علاماتك وصفحات الملف. اضغط أي عنصر للانتقال إليه.</SheetDescription>
      </SheetHeader>
      <Tabs defaultValue={bookmarks.length ? "bookmarks" : toc.length ? "toc" : "pages"} dir="rtl" className="flex-1 flex flex-col min-h-0">
        <TabsList className="mx-6 rounded-sm bg-[#171717]">
          <TabsTrigger value="bookmarks" data-testid="index-tab-bookmarks" className="rounded-sm">العلامات ({bookmarks.length})</TabsTrigger>
          <TabsTrigger value="toc" data-testid="index-tab-toc" className="rounded-sm">فهرس الكتاب</TabsTrigger>
          <TabsTrigger value="pages" data-testid="index-tab-pages" className="rounded-sm">الصفحات</TabsTrigger>
        </TabsList>
        <div className="flex-1 overflow-y-auto mt-3">
          <TabsContent value="bookmarks" className="mt-0"><BookmarksTab bookmarks={bookmarks} onJump={onJump} onDelete={onDeleteBookmark} /></TabsContent>
          <TabsContent value="toc" className="mt-0"><TocTab toc={toc} current={current} onJumpPage={onJumpPage} /></TabsContent>
          <TabsContent value="pages" className="mt-0"><PagesTab pages={pages} pageStart={pageStart} current={current} onJumpPage={onJumpPage} /></TabsContent>
        </div>
      </Tabs>
    </SheetContent>
  </Sheet>
);
