import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { api, formatApiError } from "@/lib/api";

export function useBookmarks(docId) {
  const [bookmarks, setBookmarks] = useState([]);
  const [toc, setToc] = useState([]);

  useEffect(() => {
    api.get(`/documents/${docId}/bookmarks`).then((r) => setBookmarks(r.data)).catch(() => {});
    api.get(`/documents/${docId}/toc`).then((r) => setToc(r.data.toc)).catch(() => {});
  }, [docId]);

  const add = useCallback(async (word_index, page_number, snippet) => {
    try {
      const { data } = await api.post(`/documents/${docId}/bookmarks`, { word_index, page_number, snippet });
      setBookmarks((b) => [...b, data].sort((x, y) => x.word_index - y.word_index));
      toast.success(`أُضيفت علامة — صفحة ${page_number}`);
    } catch (e) {
      toast.error(formatApiError(e));
    }
  }, [docId]);

  const remove = useCallback(async (bm) => {
    try {
      await api.delete(`/documents/${docId}/bookmarks/${bm.bookmark_id}`);
      setBookmarks((b) => b.filter((x) => x.bookmark_id !== bm.bookmark_id));
    } catch (e) {
      toast.error(formatApiError(e));
    }
  }, [docId]);

  return { bookmarks, toc, add, remove };
}
