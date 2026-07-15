"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, FileText, AlertCircle, CheckCircle2, Loader2, Image, Type, BookOpen, Lock } from "lucide-react";
import { cn, formatBytes } from "@/lib/utils";
import { uploadPdf, type UploadResponse } from "@/lib/api";
import { toast } from "sonner";

interface Props {
  onSuccess: (resp: UploadResponse) => void;
}

// "awaiting_template": DOCX recebido, aguardando o usuário escolher o template
// antes de enviar de fato — evita processar no padrão errado.
type UploadState = "idle" | "awaiting_template" | "uploading" | "queued" | "error";
type Mode = "fiel" | "texto";
type Template = "medcel" | "generico";

const TEMPLATES: { id: Template; label: string; desc: string; available: boolean }[] = [
  { id: "medcel", label: "Medcel", desc: "Padrão editorial Medcel: seções numeradas, figuras e referências.", available: true },
  { id: "generico", label: "Genérico", desc: "Conversão simples: título, parágrafos e imagens, sem padrão fixo.", available: true },
];

function isDocx(file: File) {
  return (
    file.name.toLowerCase().endsWith(".docx") ||
    file.type === "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
  );
}

export function DropzoneUpload({ onSuccess }: Props) {
  const [state, setState] = useState<UploadState>("idle");
  const [progress, setProgress] = useState(0);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [mode, setMode] = useState<Mode>("fiel");
  const [template, setTemplate] = useState<Template>("medcel");

  const handleUpload = useCallback(async (file: File, tpl?: Template) => {
    setState("uploading");
    setProgress(0);
    setErrorMsg("");
    try {
      const resp = await uploadPdf(file, mode, (pct) => setProgress(pct), tpl);
      setState("queued");
      toast.success(isDocx(file) ? "DOCX enviado! Conversão iniciada." : "PDF enviado! Conversão iniciada.");
      onSuccess(resp);
    } catch (err: unknown) {
      const errAny = err as { response?: { data?: { detail?: { message?: string } | string } } };
      const detail = errAny?.response?.data?.detail;
      const msg =
        (typeof detail === "object" && detail !== null ? detail.message : undefined) ||
        (typeof detail === "string" ? detail : undefined) ||
        "Falha no upload. Tente novamente.";
      setErrorMsg(typeof msg === "string" ? msg : JSON.stringify(msg));
      setState("error");
      toast.error("Falha no upload");
    }
  }, [onSuccess, mode]);

  const onDrop = useCallback((accepted: File[]) => {
    if (accepted.length === 0) return;
    const file = accepted[0];
    setSelectedFile(file);

    if (isDocx(file)) {
      // Word precisa de template escolhido antes de subir
      setTemplate("medcel");
      setState("awaiting_template");
      return;
    }

    handleUpload(file);
  }, [handleUpload]);

  const { getRootProps, getInputProps, isDragActive, fileRejections } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
    },
    maxFiles: 1,
    maxSize: 100 * 1024 * 1024,
    disabled: state === "uploading" || state === "queued" || state === "awaiting_template",
  });

  const resetUpload = () => {
    setState("idle");
    setSelectedFile(null);
    setProgress(0);
    setErrorMsg("");
  };

  const showModeSelector = state === "idle" && (!selectedFile || !isDocx(selectedFile));

  return (
    <div className="w-full max-w-2xl mx-auto">
      {showModeSelector && (
        <div className="mb-4 grid grid-cols-2 gap-3">
          <button
            onClick={() => setMode("fiel")}
            className={cn(
              "flex items-start gap-3 rounded-xl border p-4 text-left transition-all",
              mode === "fiel"
                ? "border-brand-500 bg-brand-500/10"
                : "border-surface-border bg-surface-card hover:border-brand-500/40"
            )}
          >
            <Image className={cn("h-5 w-5 mt-0.5", mode === "fiel" ? "text-brand-600" : "text-gray-400")} />
            <div>
              <p className="text-sm font-semibold text-ink">Modo Fiel</p>
              <p className="text-xs text-gray-500 mt-0.5">Idêntico ao PDF. Preserva layout, cores e imagens.</p>
            </div>
          </button>
          <button
            onClick={() => setMode("texto")}
            className={cn(
              "flex items-start gap-3 rounded-xl border p-4 text-left transition-all",
              mode === "texto"
                ? "border-brand-500 bg-brand-500/10"
                : "border-surface-border bg-surface-card hover:border-brand-500/40"
            )}
          >
            <Type className={cn("h-5 w-5 mt-0.5", mode === "texto" ? "text-brand-600" : "text-gray-400")} />
            <div>
              <p className="text-sm font-semibold text-ink">Modo Texto</p>
              <p className="text-xs text-gray-500 mt-0.5">Texto selecionável e ajustável. Layout livre.</p>
            </div>
          </button>
        </div>
      )}

      {/* Seletor de template — aparece só quando um DOCX é solto, antes de enviar */}
      {state === "awaiting_template" && selectedFile && (
        <div className="mb-4 rounded-xl border border-surface-border bg-surface-card p-4">
          <div className="flex items-center gap-2 mb-3">
            <FileText className="h-4 w-4 text-brand-600" />
            <p className="text-sm font-medium text-ink truncate">{selectedFile.name}</p>
          </div>

          <p className="text-xs text-gray-500 mb-3">Escolha o template editorial antes de enviar:</p>

          <div className="grid grid-cols-2 gap-3 mb-4">
            {TEMPLATES.map((t) => (
              <button
                key={t.id}
                onClick={() => t.available && setTemplate(t.id)}
                disabled={!t.available}
                className={cn(
                  "relative flex flex-col items-start gap-1 rounded-xl border p-3.5 text-left transition-all",
                  !t.available && "opacity-50 cursor-not-allowed border-surface-border bg-surface",
                  t.available && template === t.id && "border-brand-500 bg-brand-500/10",
                  t.available && template !== t.id && "border-surface-border bg-surface hover:border-brand-500/40"
                )}
              >
                {!t.available && (
                  <span className="absolute top-2.5 right-2.5 flex items-center gap-1 text-[10px] font-mono uppercase text-gray-400">
                    <Lock className="h-3 w-3" /> Em breve
                  </span>
                )}
                <div className="flex items-center gap-2">
                  <BookOpen className={cn("h-4 w-4", t.available && template === t.id ? "text-brand-600" : "text-gray-400")} />
                  <p className="text-sm font-semibold text-ink">{t.label}</p>
                </div>
                <p className="text-xs text-gray-500">{t.desc}</p>
              </button>
            ))}
          </div>

          <div className="flex gap-2">
            <button
              onClick={() => selectedFile && handleUpload(selectedFile, template)}
              className="flex-1 rounded-lg bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium py-2 transition-colors"
            >
              Enviar com template {TEMPLATES.find((t) => t.id === template)?.label}
            </button>
            <button
              onClick={resetUpload}
              className="rounded-lg border border-surface-border text-gray-500 hover:text-ink text-sm px-4 py-2 transition-colors"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}

      <div
        {...getRootProps()}
        className={cn(
          "relative overflow-hidden border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all duration-200",
          isDragActive && "border-brand-500 bg-brand-500/10",
          state === "idle" && !isDragActive && "border-surface-border hover:border-brand-500/50 hover:bg-surface-hover",
          state === "awaiting_template" && "border-surface-border bg-surface-card/50 cursor-not-allowed opacity-60",
          state === "uploading" && "border-brand-500/30 bg-brand-500/5 cursor-not-allowed",
          state === "queued" && "border-emerald-400 bg-emerald-50 cursor-not-allowed",
          state === "error" && "border-red-400 bg-red-50"
        )}
      >
        {/* Dobra de canto — referência a página de livro, grudada nesta caixa específica */}
        <div
          className="absolute top-0 right-0 w-7 h-7 pointer-events-none"
          style={{
            background: "linear-gradient(135deg, #DDDBDD 50%, transparent 50%)",
            clipPath: "polygon(100% 0, 0 0, 100% 100%)",
            borderTopRightRadius: "1rem",
          }}
          aria-hidden="true"
        />
        <input {...getInputProps()} />
        <div className="flex justify-center mb-4">
          {state === "uploading" && (
            <div className="h-14 w-14 rounded-full bg-brand-500/20 flex items-center justify-center">
              <Loader2 className="h-6 w-6 text-brand-600 animate-spin" />
            </div>
          )}
          {state === "queued" && (
            <div className="h-14 w-14 rounded-full bg-emerald-100 flex items-center justify-center">
              <CheckCircle2 className="h-6 w-6 text-emerald-600" />
            </div>
          )}
          {state === "error" && (
            <div className="h-14 w-14 rounded-full bg-red-100 flex items-center justify-center">
              <AlertCircle className="h-6 w-6 text-red-600" />
            </div>
          )}
          {(state === "idle" || state === "awaiting_template") && (
            <div className={cn("h-14 w-14 rounded-full flex items-center justify-center transition-colors", isDragActive ? "bg-brand-500/30" : "bg-surface-border")}>
              {selectedFile ? <FileText className="h-6 w-6 text-brand-600" /> : <Upload className={cn("h-6 w-6", isDragActive ? "text-brand-600" : "text-gray-400")} />}
            </div>
          )}
        </div>

        {state === "idle" && (
          <>
            <p className="text-lg font-medium text-ink mb-1">{isDragActive ? "Solte o arquivo aqui" : "Arraste um PDF ou DOCX, ou clique para selecionar"}</p>
            <p className="text-sm text-gray-500">Suporta arquivos até 100MB</p>
          </>
        )}
        {state === "awaiting_template" && (
          <>
            <p className="text-base font-medium text-ink mb-1">Escolha o template acima para continuar</p>
            <p className="text-sm text-gray-500">O envio começa depois da confirmação</p>
          </>
        )}
        {state === "uploading" && selectedFile && (
          <>
            <p className="text-base font-medium text-ink mb-1">{selectedFile.name}</p>
            <p className="text-sm text-gray-500 mb-4">{formatBytes(selectedFile.size)}</p>
            <div className="w-full max-w-xs mx-auto h-1.5 bg-surface-border rounded-full overflow-hidden">
              <div className="h-full bg-brand-500 rounded-full transition-all duration-300" style={{ width: `${progress}%` }} />
            </div>
            <p className="text-xs text-gray-500 mt-2">{progress}% enviado</p>
          </>
        )}
        {state === "queued" && (
          <>
            <p className="text-base font-medium text-emerald-700 mb-1">Arquivo recebido!</p>
            <p className="text-sm text-gray-500">Conversão iniciada — acompanhe abaixo</p>
          </>
        )}
        {state === "error" && (
          <>
            <p className="text-base font-medium text-red-700 mb-1">Falha no upload</p>
            <p className="text-sm text-gray-500 mb-3">{errorMsg}</p>
            <button onClick={(e) => { e.stopPropagation(); resetUpload(); }} className="text-xs text-brand-500 hover:text-brand-600 underline">Tentar novamente</button>
          </>
        )}
      </div>

      {fileRejections.length > 0 && (
        <p className="mt-2 text-xs text-red-600 text-center">{fileRejections[0].errors[0]?.message}</p>
      )}
    </div>
  );
}
