"use client";

import Link from "next/link";
import { BookOpen, Image as ImageIcon, ShieldCheck, KeyRound } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

const APPS = [
  {
    href: "/",
    appKey: "epub",
    tag: "EPUB",
    title: "Gerador de EPUB",
    desc: "Converta PDFs e DOCXs em EPUB3, com os templates Medcel, Genérico e Caderno de Conceitos Matadores.",
    icon: BookOpen,
  },
  {
    href: "/thumbs",
    appKey: "thumbs",
    tag: "THUMBS",
    title: "Gerador de Thumbs",
    desc: "Templates de thumbnail para lives — padrão das 3 marcas e pós-graduação.",
    icon: ImageIcon,
  },
];

export default function AppsPage() {
  const { user } = useAuth();
  // Esconde o card de apps que o usuário não tem liberado — admin sempre
  // vê tudo. Isso é só a camada de UI; o bloqueio de verdade acontece no
  // backend (rotas do EPUB) e na própria página /thumbs.
  const visibleApps = APPS.filter((app) => user?.is_admin || user?.app_access?.includes(app.appKey));

  return (
    <div className="relative min-h-screen flex flex-col items-center justify-center px-4 py-16 bg-surface">
      <div className="absolute top-5 right-5 flex items-center gap-1.5">
        <Link
          href="/conta"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-gray-500 hover:text-ink hover:bg-surface-hover transition-colors"
        >
          <KeyRound className="h-4 w-4" />
          Minha conta
        </Link>
        {user?.is_admin && (
          <Link
            href="/admin"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-gray-500 hover:text-secondary hover:bg-surface-hover transition-colors"
          >
            <ShieldCheck className="h-4 w-4" />
            Admin
          </Link>
        )}
      </div>

      <img src="/logo-afya.svg" alt="Afya" className="h-9 w-auto mb-2" />
      <p className="text-sm text-gray-500 mb-10">Escolha um aplicativo</p>

      {visibleApps.length > 0 ? (
        <div className="w-full max-w-2xl grid grid-cols-1 sm:grid-cols-2 gap-4">
          {visibleApps.map(({ href, tag, title, desc, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className="group block rounded-2xl border border-surface-border bg-surface-card p-6 transition-all hover:-translate-y-0.5 hover:shadow-lg hover:border-brand-500"
            >
              <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-500 px-3 py-1 text-[11px] font-semibold text-white mb-4">
                <Icon className="h-3 w-3" />
                {tag}
              </span>
              <h2 className="text-base font-display font-semibold text-ink mb-1.5">{title}</h2>
              <p className="text-xs text-gray-500 leading-relaxed">{desc}</p>
            </Link>
          ))}
        </div>
      ) : (
        <p className="text-sm text-gray-500 text-center max-w-sm">
          Você ainda não tem nenhum aplicativo liberado. Peça a um administrador pra liberar o acesso.
        </p>
      )}
    </div>
  );
}
