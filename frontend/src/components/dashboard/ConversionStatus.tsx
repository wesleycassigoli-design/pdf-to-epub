"use client";

import { useState } from "react";
import { useConversionStatus } from "@/hooks/useConversionStatus";
import { Loader2, CheckCircle2, XCircle, Clock, BookOpen, Download, RotateCcw, Eye } from "lucide-react";
import { downloadEpub, getErrorMessage } from "@/lib/api";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

interface Props {
  bookId: string;
  onReset?: () => void;
}

export function ConversionStatus({ bookId, onReset }: Props) {
  const { data: status, isLoading } = useConversionStatus(bookId);
  const [downloading, setDownloading] = useState(false);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      await downloadEpub(bookId);
    } catch (err) {
      toast.error(getErrorMessage(err, "Não foi possível baixar o EPUB"));
    } finally {
      setDownloading(false);
    }
  };

  if (isLoading || !status) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <Loader2 className="h-4 w-4 animate-spin" />
        Conectando...
      </div>
    );
  }

  const { book_status, progress_message, chapters_count, full_epub_ready } = status;

  const icons = {
    pending:    <Clock className="h-5 w-5 text-amber-600" />,
    processing: <Loader2 className="h-5 w-5 text-blue-600 animate-spin" />,
    done:       <CheckCircle2 className="h-5 w-5 text-emerald-600" />,
    error:      <XCircle className="h-5 w-5 text-red-600" />,
  };

  const containerColors = {
    pending:    "border-amber-200 bg-amber-50",
    processing: "border-blue-200 bg-blue-50",
    done:       "border-emerald-200 bg-emerald-50",
    error:      "border-red-200 bg-red-50",
  };

  return (
    <div className={cn(
      "rounded-xl border p-5 mt-6 animate-fade-in",
      containerColors[book_status as keyof typeof containerColors] || "border-surface-border"
    )}>
      <div className="flex items-start gap-3">
        {icons[book_status as keyof typeof icons]}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-ink">{progress_message}</p>

          {book_status === "processing" && (
            <div className="mt-2 w-full h-1 bg-surface-border rounded-full overflow-hidden">
              <div className="h-full bg-blue-500 rounded-full animate-pulse-slow w-1/2" />
            </div>
          )}

          {book_status === "done" && (
            <div className="mt-3 flex flex-wrap gap-2">
              {chapters_count > 0 && (
                <div className="flex items-center gap-1.5 text-xs text-gray-500">
                  <BookOpen className="h-3.5 w-3.5" />
                  {chapters_count} capítulo{chapters_count !== 1 ? "s" : ""} detectado{chapters_count !== 1 ? "s" : ""}
                </div>
              )}
            </div>
          )}
        </div>

        {full_epub_ready && (
          <div className="flex gap-2 flex-shrink-0">
            <button
              onClick={handleDownload}
              disabled={downloading}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-50 text-emerald-700 text-xs font-medium hover:bg-emerald-100 transition-colors disabled:opacity-50"
            >
              {downloading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
              Baixar EPUB
            </button>
            <Link
              href={`/reader/${bookId}`}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-hover text-gray-600 text-xs font-medium hover:bg-surface-border transition-colors"
            >
              <Eye className="h-3.5 w-3.5" />
              Visualizar
            </Link>
            <Link
              href={`/book/${bookId}`}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand-500/10 text-brand-600 text-xs font-medium hover:bg-brand-500/20 transition-colors"
            >
              <BookOpen className="h-3.5 w-3.5" />
              Detalhes
            </Link>
            {onReset && (
              <button
                onClick={onReset}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-hover text-gray-600 text-xs font-medium hover:bg-surface-border transition-colors"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Converter outro arquivo
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
