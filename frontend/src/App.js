import "@/App.css";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import Login from "@/pages/Login";
import Library from "@/pages/Library";
import DocumentStatus from "@/pages/DocumentStatus";
import Reader from "@/pages/Reader";
import { FullScreenLoader } from "@/components/FullScreenLoader";

function Protected({ children }) {
  const { user } = useAuth();
  if (user === null) return <FullScreenLoader />;
  if (user === false) return <Navigate to="/login" replace />;
  return children;
}

function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/library" element={<Protected><Library /></Protected>} />
      <Route path="/documents/:id" element={<Protected><DocumentStatus /></Protected>} />
      <Route path="/read/:id" element={<Protected><Reader /></Protected>} />
      <Route path="*" element={<Navigate to="/library" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <div className="App min-h-screen bg-[#0a0a0a] text-white" dir="rtl">
      <BrowserRouter>
        <AuthProvider>
          <AppRouter />
        </AuthProvider>
      </BrowserRouter>
      <Toaster theme="dark" position="bottom-left" dir="rtl" richColors />
    </div>
  );
}
