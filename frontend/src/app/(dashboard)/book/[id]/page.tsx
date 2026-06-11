"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { fetchBook, getDownloadUrl, getChapterDownloadUrl } from "@/lib/api";
import { formatBytes, formatDate, STATUS_COLOR, STATUS_LABEL } from "@/lib/utils";
import {
  ArrowLeft, Download, FileText, BookOpen, Loader2,
  AlertCircle, Calendar, Hash, Layers
} from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";

export default function BookDetailPage() {
  const params = useParams();
  const bookId = params.id as string;

  const { data: book, isLoading, isError } = useQuery({
    queryKey: ["book", bookId],
    queryFn: () => fetchBook(bookId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "processing" || status === "pending" ? 3000 : false;
    },
  });

  if (isLoading) {
    return (
      <div className="p-8 flex items-center gap-2 text-slate-400">
        <Loader2 className="h-4 w-4 animate-spin" /> Carregando...
      </div>
    );
  }

  if (isError || !book) {
    return (
      <div className="p-8 flex items-center gap-2 text-red-400">
        <AlertCircle className="h-4 w-4" /> Livro não encontrado
      </div>
    );
  }

  return (
    <div className="p-8 max-w-4xl">
      {/* Back */}
      <Link
        href="/history"
        className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-white mb-6 transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Histórico
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-6">
        <div className="flex items-start gap-4">
          <div className="h-12 w-12 rounded-xl bg-surface-border flex items-center justify-center flex-shrink-0">
            <FileText className="h-6 w-6 text-slate-400" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-white">{book.original_name}</h1>
            <span className={cn(
              "mt-1 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium",
              STATUS_COLOR[book.status]
            )}>
              {STATUS_LABEL[book.status] || book.status}
            </span>
          </div>
        </div>

        {book.status === "done" && book.full_epub && (
          <a
            href={getDownloadUrl(book.id)}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-500/20 text-emerald-400 text-sm font-medium hover:bg-emerald-500/30 transition-colors flex-shrink-0"
          >
            <Download className="h-4 w-4" />
            Baixar EPUB completo
          </a>
        )}
      </div>

      {/* Meta cards */}
      <div className="grid grid-cols-4 gap-3 mb-8">
        {[
          { icon: Hash,     label: "Páginas",    value: book.page_count ?? "—" },
          { icon: Layers,   label: "Capítulos",  value: book.chapters.length || "—" },
          { icon: FileText, label: "Tamanho",    value: formatBytes(book.file_size_bytes) },
          { icon: Calendar, label: "Convertido", value: formatDate(book.created_at) },
        ].map(({ icon: Icon, label, value }) => (
          <div key={label} className="rounded-xl border border-surface-border bg-surface-card p-4">
            <div className="flex items-center gap-2 text-slate-400 mb-1">
              <Icon className="h-3.5 w-3.5" />
              <span className="text-xs">{label}</span>
            </div>
            <p className="text-sm font-semibold text-white">{value}</p>
          </div>
        ))}
      </div>

      {/* Erro */}
      {book.status === "error" && book.error_message && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 mb-6">
          <div className="flex items-start gap-2">
            <AlertCircle className="h-4 w-4 text-red-400 mt-0.5 flex-shrink-0" />
            <p className="text-sm text-red-300">{book.error_message}</p>
          </div>
        </div>
      )}

      {/* Capítulos */}
      {book.chapters.length > 0 && (
        <div>
          <h2 className="text-base font-semibold text-white mb-3">
            Capítulos ({book.chapters.length})
          </h2>
          <div className="space-y-2">
            {book.chapters.map((ch) => (
              <div
                key={ch.id}
                className="flex items-center gap-4 rounded-xl border border-surface-border bg-surface-card px-5 py-3 hover:border-surface-hover transition-colors"
              >
                <div className="h-7 w-7 rounded-lg bg-brand-600/20 flex items-center justify-center flex-shrink-0">
                  <span className="text-xs font-bold text-brand-400">{ch.chapter_number}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-white truncate">{ch.title}</p>
                  {ch.start_page && ch.end_page && (
                    <p className="text-xs text-slate-500 mt-0.5">
                      p. {ch.start_page} – {ch.end_page} ({ch.end_page - ch.start_page + 1} páginas)
                    </p>
                  )}
                </div>
                {ch.epub_file && (
                  <a
                    href={getChapterDownloadUrl(book.id, ch.id)}
                    className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-brand-400 transition-colors"
                    title="Baixar este capítulo"
                  >
                    <Download className="h-3.5 w-3.5" />
                    EPUB
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
