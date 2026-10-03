import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { BookOpenText } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { api, formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const BG =
  "https://images.unsplash.com/photo-1705294108409-c730a280d1e0?crop=entropy&cs=srgb&fm=jpg&q=85&w=1600";

function GoogleButton() {
  const onClick = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + "/library";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };
  return (
    <Button type="button" variant="outline" onClick={onClick} data-testid="google-login-btn"
      className="w-full h-11 rounded-sm border-neutral-700 bg-transparent hover:bg-white/5 transition-colors">
      المتابعة باستخدام Google
    </Button>
  );
}

export default function Login() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ email: "", password: "", name: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/library" replace />;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const { data } = await api.post(`/auth/${mode}`, form);
      setUser(data);
      navigate("/library");
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="min-h-screen grid lg:grid-cols-2" data-testid="login-page">
      <aside className="relative hidden lg:block overflow-hidden">
        <img src={BG} alt="" className="absolute inset-0 h-full w-full object-cover" />
        <div className="absolute inset-0 bg-black/75" />
        <div className="relative h-full flex flex-col justify-end p-14 fade-up">
          <p className="text-xs font-bold tracking-[0.2em] text-[#e11d48] mb-4">قارئ · نسخة أولى</p>
          <h1 className="font-reader text-5xl xl:text-6xl font-black leading-tight">اقرأ أسرع،<br />وارجع إلى المصدر.</h1>
          <p className="mt-6 max-w-md text-neutral-300 leading-relaxed">
            ارفع ملف PDF عربياً، وسنستخرج نصه صفحةً صفحة مع كشف الصفحات المشكوك فيها بدلاً من عرض نص خاطئ بصمت.
          </p>
        </div>
      </aside>
      <main className="flex items-center justify-center p-8 sm:p-16">
        <div className="w-full max-w-sm fade-up">
          <div className="flex items-center gap-3 mb-12">
            <BookOpenText className="h-7 w-7 text-[#e11d48]" />
            <span className="text-xl font-bold">قارئ</span>
          </div>
          <h2 className="text-2xl font-bold mb-2">{mode === "login" ? "تسجيل الدخول" : "إنشاء حساب"}</h2>
          <p className="text-sm text-neutral-500 mb-8">مكتبتك الخاصة من ملفات PDF.</p>
          <form onSubmit={submit} className="space-y-5" data-testid="auth-form">
            {mode === "register" && (
              <div className="space-y-2">
                <Label htmlFor="name">الاسم</Label>
                <Input id="name" value={form.name} onChange={set("name")} data-testid="register-name-input" className="h-11 rounded-sm bg-[#171717]" />
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="email">البريد الإلكتروني</Label>
              <Input id="email" type="email" dir="ltr" required value={form.email} onChange={set("email")} data-testid="auth-email-input" className="h-11 rounded-sm bg-[#171717] text-left" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">كلمة المرور</Label>
              <Input id="password" type="password" dir="ltr" required minLength={6} value={form.password} onChange={set("password")} data-testid="auth-password-input" className="h-11 rounded-sm bg-[#171717] text-left" />
            </div>
            {error && <p className="text-sm text-red-400" data-testid="auth-error">{error}</p>}
            <Button type="submit" disabled={busy} data-testid="auth-submit-btn"
              className="w-full h-11 rounded-sm bg-[#e11d48] hover:bg-[#be123c] text-white transition-colors">
              {busy ? "…" : mode === "login" ? "دخول" : "إنشاء الحساب"}
            </Button>
          </form>
          {process.env.REACT_APP_DISABLE_GOOGLE_AUTH !== "true" && (
            <>
              <div className="my-6 flex items-center gap-3 text-xs text-neutral-600">
                <span className="h-px flex-1 bg-neutral-800" />أو<span className="h-px flex-1 bg-neutral-800" />
              </div>
              <GoogleButton />
            </>
          )}
          <button type="button" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}
            className="mt-8 text-sm text-neutral-400 hover:text-white transition-colors" data-testid="auth-toggle-mode-btn">
            {mode === "login" ? "ليس لديك حساب؟ أنشئ حساباً" : "لديك حساب؟ سجّل الدخول"}
          </button>
        </div>
      </main>
    </div>
  );
}
