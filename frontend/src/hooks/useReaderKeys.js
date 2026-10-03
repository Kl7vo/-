import { useEffect } from "react";

// B: bookmark · Space: play/pause · ←: forward (RTL) · →: back · ↑/↓: speed · PageUp/PageDown: pages
export function useReaderKeys({ r, setWpm, goPage, addBookmark }) {
  useEffect(() => {
    const onKey = (e) => {
      if (["INPUT", "TEXTAREA"].includes(e.target.tagName)) return;
      const map = {
        " ": r.toggle,
        ArrowLeft: r.forward,
        ArrowRight: r.back,
        ArrowUp: () => setWpm((w) => Math.min(5000, w + 25)),
        ArrowDown: () => setWpm((w) => Math.max(100, w - 25)),
        PageDown: () => goPage(1),
        PageUp: () => goPage(-1),
        b: addBookmark,
        B: addBookmark,
      };
      const fn = map[e.key];
      if (fn) {
        e.preventDefault();
        fn();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [r, setWpm, goPage, addBookmark]);
}
