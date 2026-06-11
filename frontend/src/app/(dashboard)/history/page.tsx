"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchBooks, getDownloadUrl, type BookListItem } from "@/lib/api";
import { formatBytes, formatDate, STATUS_COLOR, STATUS_LABEL } from "@/lib/utils";
import { BookOpen, Download, Loader2, FileText, AlertCircle } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";

export default function HistoryPage() {
  const { data: books, isLoading, isError, refetch } = useQuery({
    queryKey: ["books"],
    queryFn: fetchBooks,
    refetchInterval: (query) => {
      const hasActive = query.state.data?.some(
        (b: BookListItem) => b.status === "processing" || b.status === "pending"
      );
      return hasActive ? 3000 : false;
    },
  });

  return (
    <div className="p-8 max-w-4xl">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Histórico</h1>
          <p className="text-sm text-slate-400 mt-1">Todas as conversões realizadas</p>
        </div>
        <button
          onClick={() => refetch()}
          className="text-xs text-slate-400 hover:text-white transition-colors"
        >
          Atualizar
        </button>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center gap-2 text-slate-400">
          <Loader2 className="h-4 w-4 animate-spin" />
          Carregando...
        </div>
      )}

      {/* Erro */}
      {isError && (
        <div className="flex items-center gap-2 text-red-400 text-sm">
          <AlertCircle className="h-4 w-4" />
          Erro ao carregar histórico
        </div>
      )}

      {/* Vazio */}
      {!isLoading && books?.length === 0 && (
        <div className="text-center py-16">
          <FileText className="h-10 w-10 text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400 text-sm">Nenhuma conversão ainda</p>
          <Link href="/" className="text-brand-400 text-sm hover:underline mt-1 inline-block">
            Converter primeiro PDF
          </Link>
        </div>
      )}

      {/* Lista */}
      {books && books.length > 0 && (
        <div className="space-y-3">
          {books.map((book: BookListItem) => (
            <div
              key={book.id}
              className="rounded-xl border border-surface-border bg-surface-card p-5 flex items-center gap-4 hover:border-surface-hover transition-colors"
            >
              {/* Ícone */}
              <div className="h-10 w-10 rounded-lg bg-surface-border flex items-center justify-center flex-shrink-0">
                <FileText className="h-5 w-5 text-slate-400" />
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-white truncate">{book.original_name}</p>
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-xs text-slate-500">{formatBytes(book.file_size_bytes)}</span>
                  {book.page_count && (
                    <span className="text-xs text-slate-500">{book.page_count} páginas</span>
                  )}
                  {book.chapters_count > 0 && (
                    <span className="text-xs text-slate-500">{book.chapters_count} capítulos</span>
                  )}
                  <span className="text-xs text-slate-600">{formatDate(book.created_at)}</span>
                </div>
              </div>

              {/* Status badge */}
              <span className={cn(
                "px-2.5 py-1 rounded-full text-xs font-medium flex-shrink-0",
                STATUS_COLOR[book.status]
              )}>
                {STATUS_LABEL[book.status] || book.status}
              </span>

              {/* Ações */}
              <div className="flex items-center gap-2 flex-shrink-0">
                <Link
                  href={`/book/${book.id}`}
                  className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-surface-hover transition-colors"
                  title="Ver detalhes"
                >
                  <BookOpen className="h-4 w-4" />
                </Link>
                {book.status === "done" && (
                  <a
                    href={getDownloadUrl(book.id)}
                    className="p-2 rounded-lg text-slate-400 hover:text-emerald-400 hover:bg-emerald-500/10 transition-colors"
                    title="Baixar EPUB completo"
                  >
                    <Download className="h-4 w-4" />
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
