"use client";

import { useState } from "react";
import { DropzoneUpload } from "@/components/upload/DropzoneUpload";
import { ConversionStatus } from "@/components/dashboard/ConversionStatus";
import { FileStack, BookOpenCheck, ScanText, FileType2 } from "lucide-react";
import type { UploadResponse } from "@/lib/api";

const FEATURES = [
  { icon: FileStack,    label: "Preserva layout",  desc: "Fixed Layout com fidelidade total ao PDF" },
  { icon: BookOpenCheck, label: "Detecta capítulos", desc: "Separa e gera EPUBs individuais por capítulo" },
  { icon: ScanText,     label: "OCR automático",   desc: "Reconhece PDFs escaneados com Tesseract" },
  { icon: FileType2,    label: "Aceita Word",      desc: "Template Medcel ou conversão genérica, à sua escolha" },
];

export default function UploadPage() {
  const [conversion, setConversion] = useState<UploadResponse | null>(null);
  const [resetKey, setResetKey] = useState(0);

  const handleReset = () => {
    setConversion(null);
    setResetKey((k) => k + 1);
  };

  return (
    <div className="px-10 py-10 max-w-3xl mx-auto">
      {/* Header */}
      <div className="mb-10">
        <p className="text-[11px] font-mono uppercase tracking-[0.2em] text-brand-500 mb-2">
          Conversor
        </p>
        <h1 className="text-3xl font-display font-semibold text-ink">
          Converter para EPUB
        </h1>
        <p className="text-sm text-gray-500 mt-2 max-w-lg">
          Envie um PDF ou Word e gere um EPUB3 pronto para leitura, preservando
          a diagramação original.
        </p>
      </div>

      {/* Upload */}
      <DropzoneUpload key={resetKey} onSuccess={(resp) => setConversion(resp)} />

      {/* Status de conversão */}
      {conversion && <ConversionStatus bookId={conversion.book_id} onReset={handleReset} />}

      {/* Recursos — faixa editorial com divisores, não cards genéricos */}
      <div className="mt-14 pt-8 border-t border-surface-border grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-8">
        {FEATURES.map(({ icon: Icon, label, desc }) => (
          <div key={label}>
            <Icon className="h-4 w-4 text-brand-500 mb-2.5" strokeWidth={1.75} />
            <p className="text-xs font-semibold text-ink mb-1">{label}</p>
            <p className="text-xs text-gray-500 leading-relaxed">{desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
