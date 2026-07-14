"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Upload, History } from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/",        icon: Upload,  label: "Converter" },
  { href: "/history", icon: History, label: "Histórico" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 h-full w-56 bg-surface-card border-r border-surface-border flex flex-col z-10">
      {/* Logo — marcador de página em vez de ícone genérico de app */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-surface-border">
        <svg width="18" height="24" viewBox="0 0 18 24" className="flex-shrink-0" aria-hidden="true">
          <path d="M0 0h18v24l-9-6-9 6V0z" fill="#c99a4f" />
        </svg>
        <div>
          <p className="text-sm font-display font-semibold text-white leading-none tracking-wide">
            PDF&nbsp;→&nbsp;EPUB
          </p>
          <p className="text-[10px] text-slate-500 mt-1 uppercase tracking-wider">
            Fixed Layout
          </p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map(({ href, icon: Icon, label }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
              pathname === href
                ? "bg-brand-600/15 text-brand-400 font-medium"
                : "text-slate-400 hover:text-white hover:bg-surface-hover"
            )}
          >
            <Icon className="h-4 w-4 flex-shrink-0" />
            {label}
          </Link>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-surface-border">
        <p className="text-[11px] font-mono text-slate-500">EPUB3 Fixed Layout</p>
        <p className="text-[11px] font-mono text-slate-600">v1.0.0</p>
      </div>
    </aside>
  );
}
