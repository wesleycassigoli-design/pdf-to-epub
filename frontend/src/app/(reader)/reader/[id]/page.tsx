"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import ePub, { type Book, type Rendition, type NavItem } from "epubjs";
import {
  ArrowLeft, ChevronLeft, ChevronRight, Download, List, Loader2, AlertCircle,
} from "lucide-react";
import { fetchBook, fetchEpubArrayBuffer, downloadEpub, getErrorMessage } from "@/lib/api";
import { toast } from "sonner";

export default function ReaderPage() {
  const params = useParams();
  const bookId = params.id as string;

  const viewerRef = useRef<HTMLDivElement>(null);
  const bookRef = useRef<Book | null>(null);
  const renditionRef = useRef<Rendition | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [title, setTitle] = useState("");
  const [toc, setToc] = useState<NavItem[]>([]);
  const [showToc, setShowToc] = useState(false);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const meta = await fetchBook(bookId);
        if (cancelled) return;
        setTitle(meta.original_name);

        if (meta.status !== "done" || !meta.full_epub) {
          setError("Este livro ainda não tem um EPUB pronto para visualização.");
          setLoading(false);
          return;
        }

        const buffer = await fetchEpubArrayBuffer(bookId);
        if (cancelled || !viewerRef.current) return;

        const book = ePub(buffer);
        bookRef.current = book;

        const rendition = book.renderTo(viewerRef.current, {
          width: "100%",
          height: "100%",
          flow: "paginated",
        });
        renditionRef.current = rendition;

        await rendition.display();
        if (cancelled) return;

        const navigation = await book.loaded.navigation;
        if (cancelled) return;
        setToc(navigation.toc || []);
        setLoading(false);
      } catch (e) {
        console.error("Falha ao carregar EPUB no visualizador:", e);
        if (!cancelled) {
          setError("Não foi possível carregar o EPUB para visualização.");
          setLoading(false);
        }
      }
    }

    load();

    return () => {
      cancelled = true;
      bookRef.current?.destroy();
      bookRef.current = null;
      renditionRef.current = null;
    };
  }, [bookId]);

  const goPrev = () => renditionRef.current?.prev();
  const goNext = () => renditionRef.current?.next();

  const goToTocItem = (href: string) => {
    renditionRef.current?.display(href);
    setShowToc(false);
  };

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

  return (
    <div className="h-screen flex flex-col bg-surface">
      <header className="flex items-center justify-between gap-3 px-4 py-3 border-b border-surface-border bg-surface-card flex-shrink-0">
        <div className="flex items-center gap-3 min-w-0">
          <Link
            href={`/book/${bookId}`}
            className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-ink transition-colors flex-shrink-0"
            title="Voltar aos detalhes"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <h1 className="text-sm font-medium text-ink truncate">{title || "Visualizador"}</h1>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {toc.length > 0 && (
            <button
              onClick={() => setShowToc((s) => !s)}
              className="p-2 rounded-lg text-gray-500 hover:text-ink hover:bg-surface-hover transition-colors"
              title="Sumário"
            >
              <List className="h-4 w-4" />
            </button>
          )}
          <button
            onClick={handleDownload}
            disabled={downloading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-50 text-emerald-700 text-xs font-medium hover:bg-emerald-100 transition-colors disabled:opacity-50"
          >
            {downloading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
            Baixar
          </button>
        </div>
      </header>

      <div className="flex-1 relative overflow-hidden">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center gap-2 text-gray-500">
            <Loader2 className="h-5 w-5 animate-spin" />
            Carregando EPUB...
          </div>
        )}

        {error && !loading && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-red-600 text-sm px-4 text-center">
            <AlertCircle className="h-5 w-5" />
            {error}
          </div>
        )}

        {showToc && (
          <div className="absolute left-0 top-0 h-full w-72 bg-surface-card border-r border-surface-border shadow-lg z-10 overflow-y-auto p-4">
            <h2 className="text-xs font-semibold text-gray-500 uppercase mb-3">Sumário</h2>
            <ul className="space-y-1">
              {toc.map((item) => (
                <li key={item.href}>
                  <button
                    onClick={() => goToTocItem(item.href)}
                    className="text-left text-sm text-ink hover:text-brand-600 w-full py-1 transition-colors"
                  >
                    {item.label?.trim()}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div ref={viewerRef} className="h-full w-full" />

        {!loading && !error && (
          <>
            <button
              onClick={goPrev}
              className="absolute left-2 top-1/2 -translate-y-1/2 p-2 rounded-full bg-surface-card border border-surface-border hover:bg-surface-hover transition-colors shadow-sm"
              title="Página anterior"
            >
              <ChevronLeft className="h-5 w-5" />
            </button>
            <button
              onClick={goNext}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-full bg-surface-card border border-surface-border hover:bg-surface-hover transition-colors shadow-sm"
              title="Próxima página"
            >
              <ChevronRight className="h-5 w-5" />
            </button>
          </>
        )}
      </div>
    </div>
  );
}
