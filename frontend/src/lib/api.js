import axios from "axios";

const backendOrigin = (process.env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "");
export const API = `${backendOrigin}/api`;

export const api = axios.create({ baseURL: API, withCredentials: true, timeout: 30000 });

let refreshing = null;
api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const cfg = error.config;
    const url = cfg?.url || "";
    if (error.response?.status === 401 && !cfg?._retry && !url.includes("/auth/")) {
      cfg._retry = true;
      try {
        refreshing = refreshing || api.post("/auth/refresh");
        await refreshing;
        refreshing = null;
        return api(cfg);
      } catch (e) {
        refreshing = null;
        window.dispatchEvent(new Event("reader-auth-expired"));
      }
    }
    return Promise.reject(error);
  }
);

export function formatApiError(err) {
  const detail = err?.response?.data?.detail;
  if (detail == null) return err?.message || "حدث خطأ غير متوقع. حاول مجدداً.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((e) => e?.msg || JSON.stringify(e)).join(" ");
  if (typeof detail?.msg === "string") return detail.msg;
  return String(detail);
}

export const pageImageUrl = (docId, page) => `${API}/documents/${docId}/pages/${page}/image`;
