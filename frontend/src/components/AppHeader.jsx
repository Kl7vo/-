import { Link } from "react-router-dom";
import { BookOpenText, LogOut } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

export const AppHeader = () => {
  const { user, logout } = useAuth();
  return (
    <header className="border-b border-neutral-800 bg-[#0a0a0a]/80 backdrop-blur-xl sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-6 sm:px-10 h-16 flex items-center justify-between">
        <Link to="/library" className="flex items-center gap-3" data-testid="header-home-link">
          <BookOpenText className="h-6 w-6 text-[#e11d48]" />
          <span className="font-bold text-lg">قارئ</span>
        </Link>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-neutral-400 hidden sm:inline" data-testid="header-user-email">{user?.email}</span>
          <button onClick={logout} data-testid="logout-btn"
            className="flex items-center gap-2 text-neutral-400 hover:text-white transition-colors">
            <LogOut className="h-4 w-4" /> خروج
          </button>
        </div>
      </div>
    </header>
  );
};
