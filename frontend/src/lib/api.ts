import axios from "axios";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  timeout: 30_000,
});

export default api;

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

// ─── API calls ───────────────────────────────────────────────────────────────

export const uploadPdf = async (
  file: File,
  mode: "fiel" | "texto",
  onProgress?: (pct: number) => void,
): Promise<UploadResponse> => {
  const form = new FormData();
  form.append("file", file);
  form.append("mode", mode);

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

export const getDownloadUrl = (bookId: string) =>
  `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/download/${bookId}`;

export const getChapterDownloadUrl = (bookId: string, chapterId: string) =>
  `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/download/${bookId}/chapter/${chapterId}`;
