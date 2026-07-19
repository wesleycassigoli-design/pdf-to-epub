import axios from "axios";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  timeout: 30_000,
});

export default api;

// ─── Auth: token + interceptors ──────────────────────────────────────────────

export const AUTH_TOKEN_KEY = "auth_token";

api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem(AUTH_TOKEN_KEY);
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Códigos que invalidam a sessão atual (token deixou de ser válido) — força
// logout imediato. "ADMIN_REQUIRED" NÃO entra aqui: é só falta de permissão
// pra uma rota específica, não significa que a sessão do usuário é inválida.
const SESSION_INVALIDATING_CODES = new Set(["ACCESS_REVOKED", "PENDING_APPROVAL"]);

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const code = error.response?.data?.detail?.code;
    const sessionInvalid = status === 401 || (status === 403 && SESSION_INVALIDATING_CODES.has(code));

    if (sessionInvalid && typeof window !== "undefined") {
      localStorage.removeItem(AUTH_TOKEN_KEY);
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export function getErrorMessage(error: unknown, fallback = "Ocorreu um erro"): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (detail && typeof detail === "object" && "message" in detail) {
      return detail.message as string;
    }
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

// ─── Types ──────────────────────────────────────────────────────────────────

export interface UploadResponse {
  book_id: string;
  task_id: string;
  message: string;
}

export interface BookListItem {
  id: string;
  original_name: string;
  file_size_bytes: number | null;
  page_count: number | null;
  status: "pending" | "processing" | "done" | "error";
  created_at: string;
  chapters_count: number;
}

export interface Chapter {
  id: string;
  book_id: string;
  title: string;
  chapter_number: number;
  start_page: number | null;
  end_page: number | null;
  epub_file: string | null;
  created_at: string;
}

export interface BookDetail extends BookListItem {
  filename: string;
  original_pdf: string | null;
  full_epub: string | null;
  error_message: string | null;
  updated_at: string;
  chapters: Chapter[];
}

export interface StatusResponse {
  book_id: string;
  book_status: string;
  conversion_status: string | null;
  task_id: string | null;
  progress_message: string;
  chapters_count: number;
  full_epub_ready: boolean;
}

export interface User {
  id: string;
  full_name: string;
  email: string;
  status: "pending" | "approved" | "revoked";
  is_admin: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

// ─── API calls ───────────────────────────────────────────────────────────────

export const uploadPdf = async (
  file: File,
  mode: "fiel" | "texto",
  onProgress?: (pct: number) => void,
  template?: "medcel" | "generico" | "caderno_conceitos_matadores",
): Promise<UploadResponse> => {
  const form = new FormData();
  form.append("file", file);
  form.append("mode", mode);
  if (template) {
    form.append("template", template);
  }

  const { data } = await api.post<UploadResponse>("/upload/", form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => {
      if (onProgress && e.total) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    },
  });
  return data;
};

export const fetchBooks = async (): Promise<BookListItem[]> => {
  const { data } = await api.get<BookListItem[]>("/books");
  return data;
};

export const fetchBook = async (id: string): Promise<BookDetail> => {
  const { data } = await api.get<BookDetail>(`/books/${id}`);
  return data;
};

export const fetchStatus = async (id: string): Promise<StatusResponse> => {
  const { data } = await api.get<StatusResponse>(`/status/${id}`);
  return data;
};

export const fetchChapters = async (bookId: string): Promise<Chapter[]> => {
  const { data } = await api.get<Chapter[]>(`/chapters/${bookId}`);
  return data;
};

// Downloads passam pelo axios (não por <a href> direto) porque as rotas de
// download exigem o header Authorization — uma navegação direta do browser
// não manda esse header.
async function downloadViaBlob(url: string, fallbackFilename: string): Promise<void> {
  const response = await api.get(url, { responseType: "blob" });
  const disposition = response.headers["content-disposition"] as string | undefined;
  let filename = fallbackFilename;
  if (disposition) {
    // O backend (Starlette FileResponse) usa urllib.parse.quote() internamente
    // e só manda filename="..." puro quando o nome bate 100% com o resultado
    // do quote — ou seja, sem espaço, acento, parêntese etc. Como isso é raro
    // em nome de arquivo real, quase sempre vem no formato RFC 5987
    // (filename*=UTF-8''nome%20codificado), que precisa ser decodificado à
    // parte; checar esse formato primeiro e só cair no formato simples como
    // segundo caso.
    const rfc5987 = disposition.match(/filename\*=(?:UTF-8|utf-8)''([^;]+)/);
    if (rfc5987) {
      filename = decodeURIComponent(rfc5987[1]);
    } else {
      const plain = disposition.match(/filename="?([^";]+)"?/);
      if (plain) filename = plain[1];
    }
  }

  const blobUrl = URL.createObjectURL(response.data);
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(blobUrl);
}

export const downloadEpub = (bookId: string, fallbackFilename = "livro.epub") =>
  downloadViaBlob(`/download/${bookId}`, fallbackFilename);

export const downloadChapterEpub = (bookId: string, chapterId: string, fallbackFilename = "capitulo.epub") =>
  downloadViaBlob(`/download/${bookId}/chapter/${chapterId}`, fallbackFilename);

// Usado pelo visualizador (/reader/[id]) — mesmo endpoint autenticado do
// download, só que como ArrayBuffer em memória (epub.js) em vez de salvar
// no disco.
export const fetchEpubArrayBuffer = async (bookId: string): Promise<ArrayBuffer> => {
  const { data } = await api.get(`/download/${bookId}`, { responseType: "arraybuffer" });
  return data;
};

// ─── Auth API ────────────────────────────────────────────────────────────────

export const registerUser = async (payload: {
  full_name: string;
  email: string;
  password: string;
  privacy_accepted: boolean;
}): Promise<{ message: string; status: string }> => {
  const { data } = await api.post("/auth/register", payload);
  return data;
};

export const loginUser = async (email: string, password: string): Promise<AuthResponse> => {
  const { data } = await api.post<AuthResponse>("/auth/login", { email, password });
  return data;
};

export const fetchMe = async (): Promise<User> => {
  const { data } = await api.get<User>("/auth/me");
  return data;
};

// ─── Admin API ───────────────────────────────────────────────────────────────

export const fetchAdminUsers = async (): Promise<User[]> => {
  const { data } = await api.get<User[]>("/admin/users");
  return data;
};

export const approveUser = async (userId: string): Promise<User> => {
  const { data } = await api.post<User>(`/admin/users/${userId}/approve`);
  return data;
};

export const revokeUser = async (userId: string): Promise<User> => {
  const { data } = await api.post<User>(`/admin/users/${userId}/revoke`);
  return data;
};

export const promoteUser = async (userId: string): Promise<User> => {
  const { data } = await api.post<User>(`/admin/users/${userId}/promote`);
  return data;
};
