import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { api, formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { FullScreenLoader } from "@/components/FullScreenLoader";

export default function AuthCallback() {
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const processed = useRef(false);

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;
    const params = new URLSearchParams(window.location.hash.slice(1));
    const sessionId = params.get("session_id");
    (async () => {
      try {
        const { data } = await api.post("/auth/google/session", { session_id: sessionId });
        setUser(data);
        window.history.replaceState(null, "", "/library");
        navigate("/library", { replace: true, state: { user: data } });
      } catch (e) {
        toast.error(formatApiError(e));
        setUser(false);
        navigate("/login", { replace: true });
      }
    })();
  }, [navigate, setUser]);

  return <FullScreenLoader label="جارٍ تسجيل الدخول…" />;
}
