"use client";

import { useConversionStatus } from "@/hooks/useConversionStatus";
import { Loader2, CheckCircle2, XCircle, Clock, BookOpen, Download } from "lucide-react";
import { getDownloadUrl } from "@/lib/api";
import Link from "next/link";
import { cn } from "@/lib/utils";

interface Props {
  bookId: string;
}

export function ConversionStatus({ bookId }: Props) {
  const { data: status, isLoading } = useConversionStatus(bookId);

  if (isLoading || !status) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-400">
        <Loader2 className="h-4 w-4 animate-spin" />
        Conectando...
      </div>
    );
  }

  const { book_status, progress_message, chapters_count, full_epub_ready } = status;

  const icons = {
    pending:    <Clock className="h-5 w-5 text-amber-400" />,
    processing: <Loader2 className="h-5 w-5 text-blue-400 animate-spin" />,
    done:       <CheckCircle2 className="h-5 w-5 text-emerald-400" />,
    error:      <XCircle className="h-5 w-5 text-red-400" />,
  };

  const containerColors = {
    pending:    "border-amber-500/20 bg-amber-500/5",
    processing: "border-blue-500/20 bg-blue-500/5",
    done:       "border-emerald-500/20 bg-emerald-500/5",
    error:      "border-red-500/20 bg-red-500/5",
  };

  return (
    <div className={cn(
      "rounded-xl border p-5 mt-6 animate-fade-in",
      containerColors[book_status as keyof typeof containerColors] || "border-surface-border"
    )}>
      <div className="flex items-start gap-3">
        {icons[book_status as keyof typeof icons]}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-white">{progress_message}</p>

          {book_status === "processing" && (
            <div className="mt-2 w-full h-1 bg-surface-border rounded-full overflow-hidden">
              <div className="h-full bg-blue-500 rounded-full animate-pulse-slow w-1/2" />
            </div>
          )}

          {book_status === "done" && (
            <div className="mt-3 flex flex-wrap gap-2">
              {chapters_count > 0 && (
                <div className="flex items-center gap-1.5 text-xs text-slate-400">
                  <BookOpen className="h-3.5 w-3.5" />
                  {chapters_count} capítulo{chapters_count !== 1 ? "s" : ""} detectado{chapters_count !== 1 ? "s" : ""}
                </div>
              )}
            </div>
          )}
        </div>

        {full_epub_ready && (
          <div className="flex gap-2 flex-shrink-0">
            <a
              href={getDownloadUrl(bookId)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/20 text-emerald-400 text-xs font-medium hover:bg-emerald-500/30 transition-colors"
            >
              <Download className="h-3.5 w-3.5" />
              Baixar EPUB
            </a>
            <Link
              href={`/book/${bookId}`}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand-600/20 text-brand-400 text-xs font-medium hover:bg-brand-600/30 transition-colors"
            >
              <BookOpen className="h-3.5 w-3.5" />
              Detalhes
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
