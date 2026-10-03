import { Loader2 } from "lucide-react";

export const FullScreenLoader = ({ label = "جارٍ التحميل…" }) => (
  <div className="min-h-screen flex items-center justify-center gap-3 text-neutral-400" data-testid="fullscreen-loader">
    <Loader2 className="h-5 w-5 animate-spin" />
    <span className="text-sm">{label}</span>
  </div>
);
