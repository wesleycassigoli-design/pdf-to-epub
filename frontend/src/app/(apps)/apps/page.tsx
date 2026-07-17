"use client";

import Link from "next/link";
import { BookOpen, Image as ImageIcon } from "lucide-react";

const APPS = [
  {
    href: "/",
    tag: "EPUB",
    title: "Gerador de EPUB",
    desc: "Converta PDFs e DOCXs em EPUB3, com os templates Medcel, Genérico e Caderno de Conceitos Matadores.",
    icon: BookOpen,
  },
  {
    href: "/thumbs",
    tag: "THUMBS",
    title: "Gerador de Thumbs",
    desc: "Templates de thumbnail para lives — padrão das 3 marcas e pós-graduação.",
    icon: ImageIcon,
  },
];

export default function AppsPage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-16 bg-surface">
      <img src="/logo-afya.svg" alt="Afya" className="h-9 w-auto mb-2" />
      <p className="text-sm text-gray-500 mb-10">Escolha um aplicativo</p>

      <div className="w-full max-w-2xl grid grid-cols-1 sm:grid-cols-2 gap-4">
        {APPS.map(({ href, tag, title, desc, icon: Icon }) => (
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
    </div>
  );
}
