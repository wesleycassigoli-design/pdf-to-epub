"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import ePub, { type Book, type Rendition, type NavItem } from "epubjs";
import {
  ArrowLeft, ChevronLeft, ChevronRight, Download, List, Loader2, AlertCircle,
  Pencil, Bold, Italic, Save, X,
} from "lucide-react";
import { fetchBook, fetchEpubArrayBuffer, saveBookEdits, base64ToArrayBuffer, getErrorMessage } from "@/lib/api";
import { toast } from "sonner";

interface PendingTextEdit {
  type: "text";
  editId: string;
  html: string;
}

interface PendingImageEdit {
  type: "image";
  editId: string;
  file: File;
  previewUrl: string;
}

type PendingEdit = PendingTextEdit | PendingImageEdit;

const EDITOR_STYLE_ID = "__pdf_epub_editor_styles__";
const EDITOR_CSS = `
  body.pdf-epub-edit-mode [data-edit-id] { cursor: pointer; }
  body.pdf-epub-edit-mode [data-edit-id]:hover { outline: 2px dashed #D31C5B; outline-offset: 2px; }
  [data-edit-id][contenteditable="true"] { outline: 2px solid #D31C5B; outline-offset: 2px; background: rgba(211,28,91,0.05); }
  [data-edit-id].pdf-epub-edited { outline: 2px solid #16a34a; outline-offset: 2px; background: rgba(22,163,74,0.06); }
`;

export default function ReaderPage() {
  const params = useParams();
  const bookId = params.id as string;

  const viewerRef = useRef<HTMLDivElement>(null);
  const bookRef = useRef<Book | null>(null);
  const renditionRef = useRef<Rendition | null>(null);
  const originalBufferRef = useRef<ArrayBuffer | null>(null);
  const editModeRef = useRef(false);
  const activeEditingDocRef = useRef<Document | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pendingImageTargetRef = useRef<{ editId: string; el: HTMLImageElement } | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [title, setTitle] = useState("");
  const [toc, setToc] = useState<NavItem[]>([]);
  const [showToc, setShowToc] = useState(false);

  const [hasEditableContent, setHasEditableContent] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [isEditingText, setIsEditingText] = useState(false);
  const [pendingEdits, setPendingEdits] = useState<Map<string, PendingEdit>>(new Map());
  const [saving, setSaving] = useState(false);

  const attachContentHandlers = useCallback((contents: any) => {
    const doc: Document = contents.document;
    if (!doc) return;

    if (!doc.getElementById(EDITOR_STYLE_ID)) {
      const style = doc.createElement("style");
      style.id = EDITOR_STYLE_ID;
      style.textContent = EDITOR_CSS;
      doc.head.appendChild(style);
    }
    doc.body.classList.toggle("pdf-epub-edit-mode", editModeRef.current);

    const editableEls = doc.querySelectorAll("[data-edit-id]");
    setHasEditableContent(editableEls.length > 0);

    editableEls.forEach((el) => {
      el.addEventListener("click", (e) => {
        if (!editModeRef.current) return;
        const tag = el.tagName.toLowerCase();
        const editId = el.getAttribute("data-edit-id") || "";

        if (tag === "img") {
          pendingImageTargetRef.current = { editId, el: el as HTMLImageElement };
          fileInputRef.current?.click();
          return;
        }

        if (el.getAttribute("contenteditable") === "true") return;

        el.setAttribute("contenteditable", "true");
        (el as HTMLElement).focus();
        activeEditingDocRef.current = doc;
        setIsEditingText(true);

        const commit = () => {
          el.removeAttribute("contenteditable");
          el.classList.add("pdf-epub-edited");
          activeEditingDocRef.current = null;
          setIsEditingText(false);
          setPendingEdits((prev) => {
            const next = new Map(prev);
            next.set(editId, { type: "text", editId, html: (el as HTMLElement).innerHTML });
            return next;
          });
          el.removeEventListener("blur", commit);
        };
        el.addEventListener("blur", commit);
      });
    });
  }, []);

  const initBook = useCallback(async (buffer: ArrayBuffer) => {
    bookRef.current?.destroy();
    if (!viewerRef.current) return;

    const book = ePub(buffer);
    bookRef.current = book;

    const rendition = book.renderTo(viewerRef.current, {
      width: "100%",
      height: "100%",
      flow: "paginated",
    });
    renditionRef.current = rendition;
    rendition.hooks.content.register(attachContentHandlers);

    await rendition.display();
    const navigation = await book.loaded.navigation;
    setToc(navigation.toc || []);
  }, [attachContentHandlers]);

  const reloadBook = useCallback(async (forceRefetch: boolean) => {
    let buffer = originalBufferRef.current;
    if (forceRefetch || !buffer) {
      buffer = await fetchEpubArrayBuffer(bookId);
      originalBufferRef.current = buffer;
    }
    await initBook(buffer);
  }, [bookId, initBook]);

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
        if (cancelled) return;
        originalBufferRef.current = buffer;

        await initBook(buffer);
        if (cancelled) return;
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
      pendingEdits.forEach((edit) => {
        if (edit.type === "image") URL.revokeObjectURL(edit.previewUrl);
      });
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bookId]);

  // Mantém o ref sincronizado e alterna a classe de modo-edição no(s)
  // documento(s) já renderizados (o hook de content só roda de novo em nova
  // seção — como o EPUB tem 1 seção só, isso cobre a troca em tempo real).
  useEffect(() => {
    editModeRef.current = editMode;
    const rendition = renditionRef.current as any;
    const contents = rendition?.getContents ? rendition.getContents() : null;
    const list = Array.isArray(contents) ? contents : contents ? [contents] : [];
    list.forEach((c: any) => {
      c.document?.body?.classList.toggle("pdf-epub-edit-mode", editMode);
    });
  }, [editMode]);

  const goPrev = () => renditionRef.current?.prev();
  const goNext = () => renditionRef.current?.next();

  const goToTocItem = (href: string) => {
    renditionRef.current?.display(href);
    setShowToc(false);
  };

  // Baixa a partir do MESMO buffer já carregado no visualizador (a leitura
  // inicial ou, logo após salvar, os bytes recém-editados) — não depende de
  // um novo GET /download, que pode levar alguns segundos pra refletir uma
  // sobrescrita recém-feita no Storage (ver saveBookEdits/epub_base64).
  const handleDownload = () => {
    const buffer = originalBufferRef.current;
    if (!buffer) return;
    const blob = new Blob([buffer], { type: "application/epub+zip" });
    const filename = title ? `${title.replace(/\.[^./]+$/, "")}.epub` : "livro.epub";
    const blobUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(blobUrl);
  };

  const handleImageFileSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    const target = pendingImageTargetRef.current;
    e.target.value = "";
    if (!file || !target) return;

    const previewUrl = URL.createObjectURL(file);
    target.el.setAttribute("src", previewUrl);
    target.el.classList.add("pdf-epub-edited");

    setPendingEdits((prev) => {
      const next = new Map(prev);
      const existing = prev.get(target.editId);
      if (existing?.type === "image") URL.revokeObjectURL(existing.previewUrl);
      next.set(target.editId, { type: "image", editId: target.editId, file, previewUrl });
      return next;
    });
  };

  const handleToggleEditMode = () => {
    if (editMode && pendingEdits.size > 0) {
      const ok = window.confirm("Sair do modo edição vai descartar as alterações não salvas. Continuar?");
      if (!ok) return;
      handleDiscardEdits();
      return;
    }
    setEditMode((v) => !v);
  };

  const handleDiscardEdits = async () => {
    pendingEdits.forEach((edit) => {
      if (edit.type === "image") URL.revokeObjectURL(edit.previewUrl);
    });
    setPendingEdits(new Map());
    setEditMode(false);
    await reloadBook(false);
  };

  const handleSaveEdits = async () => {
    if (pendingEdits.size === 0) return;
    setSaving(true);
    try {
      const editsPayload: Record<string, unknown>[] = [];
      const formData = new FormData();
      let fileIndex = 0;

      for (const edit of pendingEdits.values()) {
        if (edit.type === "text") {
          editsPayload.push({ type: "text", edit_id: edit.editId, html: edit.html });
        } else {
          editsPayload.push({ type: "image", edit_id: edit.editId, file_index: fileIndex });
          formData.append("files", edit.file);
          fileIndex += 1;
        }
      }
      formData.append("edits", JSON.stringify(editsPayload));

      const result = await saveBookEdits(bookId, formData);
      toast.success(result.message || "Alterações salvas com sucesso");

      pendingEdits.forEach((edit) => {
        if (edit.type === "image") URL.revokeObjectURL(edit.previewUrl);
      });
      setPendingEdits(new Map());
      setEditMode(false);

      // Usa os bytes já editados que vieram na própria resposta, em vez de
      // buscar de novo via GET /download — o Storage pode levar alguns
      // segundos pra refletir a sobrescrita numa leitura imediata.
      const freshBuffer = base64ToArrayBuffer(result.epub_base64);
      originalBufferRef.current = freshBuffer;
      await initBook(freshBuffer);
    } catch (err) {
      toast.error(getErrorMessage(err, "Não foi possível salvar as alterações"));
    } finally {
      setSaving(false);
    }
  };

  const execFormat = (command: "bold" | "italic") => {
    activeEditingDocRef.current?.execCommand(command);
  };

  return (
    <div className="h-screen flex flex-col bg-surface">
      <input
        ref={fileInputRef}
        type="file"
        accept="image/png,image/jpeg"
        className="hidden"
        onChange={handleImageFileSelected}
      />

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
          {editMode && (
            <span className="flex-shrink-0 text-[11px] font-medium px-2 py-0.5 rounded-full bg-brand-500/10 text-brand-600">
              Editando
            </span>
          )}
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

          {hasEditableContent && !editMode && (
            <button
              onClick={handleToggleEditMode}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-hover text-gray-600 text-xs font-medium hover:bg-surface-border transition-colors"
            >
              <Pencil className="h-3.5 w-3.5" />
              Editar
            </button>
          )}

          {editMode && (
            <>
              <button
                onClick={handleDiscardEdits}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-hover text-gray-600 text-xs font-medium hover:bg-surface-border transition-colors"
              >
                <X className="h-3.5 w-3.5" />
                Descartar
              </button>
              <button
                onClick={handleSaveEdits}
                disabled={saving || pendingEdits.size === 0}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand-500 text-white text-xs font-medium hover:bg-brand-600 transition-colors disabled:opacity-50"
              >
                {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                Salvar alterações{pendingEdits.size > 0 ? ` (${pendingEdits.size})` : ""}
              </button>
            </>
          )}

          <button
            onClick={handleDownload}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-50 text-emerald-700 text-xs font-medium hover:bg-emerald-100 transition-colors"
          >
            <Download className="h-3.5 w-3.5" />
            Baixar
          </button>
        </div>
      </header>

      {isEditingText && (
        <div className="flex items-center gap-1 px-4 py-1.5 border-b border-surface-border bg-surface-card flex-shrink-0">
          <button
            onMouseDown={(e) => { e.preventDefault(); execFormat("bold"); }}
            className="p-1.5 rounded-md text-gray-600 hover:text-ink hover:bg-surface-hover transition-colors"
            title="Negrito"
          >
            <Bold className="h-3.5 w-3.5" />
          </button>
          <button
            onMouseDown={(e) => { e.preventDefault(); execFormat("italic"); }}
            className="p-1.5 rounded-md text-gray-600 hover:text-ink hover:bg-surface-hover transition-colors"
            title="Itálico"
          >
            <Italic className="h-3.5 w-3.5" />
          </button>
          <span className="text-xs text-gray-500 ml-2">Editando texto — clique fora para concluir</span>
        </div>
      )}

      {editMode && !isEditingText && (
        <div className="px-4 py-1.5 border-b border-surface-border bg-brand-500/5 flex-shrink-0">
          <span className="text-xs text-gray-600">
            Clique num texto ou imagem destacado para editar. {pendingEdits.size} {pendingEdits.size !== 1 ? "alterações pendentes" : "alteração pendente"}.
          </span>
        </div>
      )}

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
