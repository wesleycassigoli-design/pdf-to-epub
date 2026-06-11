"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, FileText, AlertCircle, CheckCircle2, Loader2 } from "lucide-react";
import { cn, formatBytes } from "@/lib/utils";
import { uploadPdf, type UploadResponse } from "@/lib/api";
import { toast } from "sonner";

interface Props {
  onSuccess: (resp: UploadResponse) => void;
}

type UploadState = "idle" | "uploading" | "queued" | "error";

export function DropzoneUpload({ onSuccess }: Props) {
  const [state, setState] = useState<UploadState>("idle");
  const [progress, setProgress] = useState(0);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  const handleUpload = useCallback(async (file: File) => {
    setState("uploading");
    setProgress(0);
    setErrorMsg("");

    try {
      const resp = await uploadPdf(file, (pct) => setProgress(pct));
      setState("queued");
      toast.success("PDF enviado! Conversão iniciada.");
      onSuccess(resp);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: { message?: string } | string } } })
          ?.response?.data?.detail?.message ||
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Falha no upload. Tente novamente.";
      setErrorMsg(typeof msg === "string" ? msg : JSON.stringify(msg));
      setState("error");
      toast.error("Falha no upload");
    }
  }, [onSuccess]);

  const onDrop = useCallback(
    (accepted: File[]) => {
      if (accepted.length === 0) return;
      const file = accepted[0];
      setSelectedFile(file);
      handleUpload(file);
    },
    [handleUpload]
  );

  const { getRootProps, getInputProps, isDragActive, fileRejections } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"] },
    maxFiles: 1,
    maxSize: 100 * 1024 * 1024, // 100MB
    disabled: state === "uploading" || state === "queued",
  });

  const resetUpload = () => {
    setState("idle");
    setSelectedFile(null);
    setProgress(0);
    setErrorMsg("");
  };

  return (
    <div className="w-full max-w-2xl mx-auto">
      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={cn(
          "relative border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all duration-200",
          isDragActive && "border-brand-500 bg-brand-600/10",
          state === "idle" && !isDragActive && "border-surface-border hover:border-brand-500/50 hover:bg-surface-hover",
          state === "uploading" && "border-brand-500/30 bg-brand-600/5 cursor-not-allowed",
          state === "queued" && "border-emerald-500/50 bg-emerald-500/5 cursor-not-allowed",
          state === "error" && "border-red-500/50 bg-red-500/5",
        )}
      >
        <input {...getInputProps()} />

        {/* Ícone central */}
        <div className="flex justify-center mb-4">
          {state === "uploading" && (
            <div className="h-14 w-14 rounded-full bg-brand-600/20 flex items-center justify-center">
              <Loader2 className="h-6 w-6 text-brand-400 animate-spin" />
            </div>
          )}
          {state === "queued" && (
            <div className="h-14 w-14 rounded-full bg-emerald-500/20 flex items-center justify-center">
              <CheckCircle2 className="h-6 w-6 text-emerald-400" />
            </div>
          )}
          {state === "error" && (
            <div className="h-14 w-14 rounded-full bg-red-500/20 flex items-center justify-center">
              <AlertCircle className="h-6 w-6 text-red-400" />
            </div>
          )}
          {state === "idle" && (
            <div className={cn(
              "h-14 w-14 rounded-full flex items-center justify-center transition-colors",
              isDragActive ? "bg-brand-600/30" : "bg-surface-border"
            )}>
              {selectedFile ? (
                <FileText className="h-6 w-6 text-brand-400" />
              ) : (
                <Upload className={cn("h-6 w-6", isDragActive ? "text-brand-400" : "text-slate-400")} />
              )}
            </div>
          )}
        </div>

        {/* Texto */}
        {state === "idle" && (
          <>
            <p className="text-lg font-medium text-white mb-1">
              {isDragActive ? "Solte o PDF aqui" : "Arraste um PDF ou clique para selecionar"}
            </p>
            <p className="text-sm text-slate-400">Suporta arquivos até 100MB</p>
          </>
        )}

        {state === "uploading" && selectedFile && (
          <>
            <p className="text-base font-medium text-white mb-1">{selectedFile.name}</p>
            <p className="text-sm text-slate-400 mb-4">{formatBytes(selectedFile.size)}</p>
            {/* Barra de progresso */}
            <div className="w-full max-w-xs mx-auto h-1.5 bg-surface-border rounded-full overflow-hidden">
              <div
                className="h-full bg-brand-500 rounded-full transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="text-xs text-slate-500 mt-2">{progress}% enviado</p>
          </>
        )}

        {state === "queued" && (
          <>
            <p className="text-base font-medium text-emerald-400 mb-1">PDF recebido!</p>
            <p className="text-sm text-slate-400">Conversão iniciada — acompanhe abaixo</p>
          </>
        )}

        {state === "error" && (
          <>
            <p className="text-base font-medium text-red-400 mb-1">Falha no upload</p>
            <p className="text-sm text-slate-400 mb-3">{errorMsg}</p>
            <button
              onClick={(e) => { e.stopPropagation(); resetUpload(); }}
              className="text-xs text-brand-400 hover:text-brand-300 underline"
            >
              Tentar novamente
            </button>
          </>
        )}
      </div>

      {/* Rejeições */}
      {fileRejections.length > 0 && (
        <p className="mt-2 text-xs text-red-400 text-center">
          {fileRejections[0].errors[0]?.message}
        </p>
      )}
    </div>
  );
}
