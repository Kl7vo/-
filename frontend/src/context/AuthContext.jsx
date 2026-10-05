import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  // null = checking, object = authenticated, false = anonymous
  const [user, setUser] = useState(null);

  const checkAuth = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
    } catch {
      try {
        const { data } = await api.post("/auth/refresh");
        setUser(data);
      } catch {
        setUser(false);
      }
    }
  }, []);

  useEffect(() => {
    checkAuth();
    const onExpired = () => setUser(false);
    window.addEventListener("reader-auth-expired", onExpired);
    return () => window.removeEventListener("reader-auth-expired", onExpired);
  }, [checkAuth]);

  const logout = async () => {
    try {
      await api.post("/auth/logout");
    } finally {
      setUser(false);
    }
  };

  return <AuthContext.Provider value={{ user, setUser, logout, checkAuth }}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
