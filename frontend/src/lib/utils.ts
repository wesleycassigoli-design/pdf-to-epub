import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatBytes(bytes: number | null | undefined): string {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

export const STATUS_LABEL: Record<string, string> = {
  pending:    "Aguardando",
  processing: "Convertendo",
  done:       "Concluído",
  error:      "Erro",
};

export const STATUS_COLOR: Record<string, string> = {
  pending:    "text-amber-400 bg-amber-400/10",
  processing: "text-blue-400 bg-blue-400/10",
  done:       "text-emerald-400 bg-emerald-400/10",
  error:      "text-red-400 bg-red-400/10",
};
