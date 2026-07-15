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
  pending:    "text-amber-700 bg-amber-50",
  processing: "text-blue-700 bg-blue-50",
  done:       "text-emerald-700 bg-emerald-50",
  error:      "text-red-700 bg-red-50",
};

export const USER_STATUS_LABEL: Record<string, string> = {
  pending:  "Pendente",
  approved: "Aprovado",
  revoked:  "Revogado",
};

export const USER_STATUS_COLOR: Record<string, string> = {
  pending:  "text-amber-700 bg-amber-50",
  approved: "text-emerald-700 bg-emerald-50",
  revoked:  "text-red-700 bg-red-50",
};
