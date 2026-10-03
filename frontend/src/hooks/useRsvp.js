import { useCallback, useEffect, useRef, useState } from "react";
import { wordDuration } from "@/lib/rsvp";

// Playback engine: every word advances on its own timer, even inside multi-word groups.
export function useRsvp({ words, groups, groupOf, wpm, punct, initialIdx, onMarker }) {
  const [idx, setIdx] = useState(initialIdx || 0);
  const [playing, setPlaying] = useState(false);
  const markerRef = useRef(onMarker);
  markerRef.current = onMarker;

  useEffect(() => {
    if (!playing || !words.length) return;
    const w = words[idx];
    if (w?.m) {
      setPlaying(false);
      markerRef.current?.(w);
      return;
    }
    if (idx >= words.length - 1) {
      const t = setTimeout(() => setPlaying(false), wordDuration(w.t, wpm, punct));
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setIdx((i) => Math.min(i + 1, words.length - 1)), wordDuration(w.t, wpm, punct));
    return () => clearTimeout(t);
  }, [playing, idx, words, wpm, punct]);

  const play = useCallback(() => {
    if (!words.length) return;
    setIdx((i) => {
      if (i >= words.length - 1) return words[i]?.m ? i : 0;
      return words[i]?.m ? i + 1 : i;
    });
    setPlaying(true);
  }, [words]);

  const toggle = useCallback(() => (playing ? setPlaying(false) : play()), [playing, play]);

  const forward = useCallback(() => {
    const g = groupOf[idx];
    if (g + 1 < groups.length) setIdx(groups[g + 1][0]);
  }, [idx, groups, groupOf]);

  const back = useCallback(() => {
    const g = groupOf[idx];
    if (!groups.length) return;
    if (idx > groups[g][0]) setIdx(groups[g][0]);
    else if (g > 0) setIdx(groups[g - 1][0]);
  }, [idx, groups, groupOf]);

  const seek = useCallback((i) => setIdx(Math.max(0, Math.min(i, words.length - 1))), [words.length]);

  return { idx, playing, setPlaying, toggle, forward, back, seek };
}
