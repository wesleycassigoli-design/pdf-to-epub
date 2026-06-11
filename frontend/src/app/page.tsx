"use client";

import { useState } from "react";
import { DropzoneUpload } from "@/components/upload/DropzoneUpload";
import { ConversionStatus } from "@/components/dashboard/ConversionStatus";
import type { UploadResponse } from "@/lib/api";

export default function UploadPage() {
  const [conversion, setConversion] = useState<UploadResponse | null>(null);

  return (
    <div className="p-8 max-w-3xl">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-white">Converter PDF</h1>
        <p className="text-sm text-slate-400 mt-1">
          Envie um PDF e gere EPUB3 Fixed Layout com layout preservado
        </p>
      </div>

      {/* Upload */}
      <DropzoneUpload onSuccess={(resp) => setConversion(resp)} />

      {/* Status de conversão */}
      {conversion && (
        <ConversionStatus bookId={conversion.book_id} />
      )}

      {/* Info cards */}
      <div className="mt-10 grid grid-cols-3 gap-4">
        {[
          { label: "Preserva layout", desc: "EPUB3 Fixed Layout com fidelidade total ao PDF" },
          { label: "Detecta capítulos", desc: "Separa automaticamente capítulos e gera EPUBs individuais" },
          { label: "OCR automático", desc: "Reconhece PDFs escaneados com Tesseract" },
        ].map(({ label, desc }) => (
          <div key={label} className="rounded-xl border border-surface-border bg-surface-card p-4">
            <p className="text-xs font-semibold text-brand-400 mb-1">{label}</p>
            <p className="text-xs text-slate-400 leading-relaxed">{desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
