"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Upload, History, ShieldCheck, LogOut, ArrowLeft } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";

const navItems = [
  { href: "/",        icon: Upload,  label: "Converter" },
  { href: "/history", icon: History, label: "Histórico" },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <aside className="fixed left-0 top-0 h-full w-56 bg-surface-card border-r border-surface-border flex flex-col z-10">
      {/* Logo Afya */}
      <div className="flex items-center px-5 py-5 border-b border-surface-border">
        <img src="/logo-afya.svg" alt="Afya" className="h-8 w-auto flex-shrink-0" />
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        <Link
          href="/apps"
          className="flex items-center gap-3 px-3 py-2 mb-2 rounded-lg text-sm text-gray-500 hover:text-ink hover:bg-surface-hover transition-colors"
        >
          <ArrowLeft className="h-4 w-4 flex-shrink-0" />
          Aplicativos
        </Link>

        {navItems.map(({ href, icon: Icon, label }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
              pathname === href
                ? "bg-brand-500/10 text-brand-600 font-medium"
                : "text-gray-500 hover:text-ink hover:bg-surface-hover"
            )}
          >
            <Icon className="h-4 w-4 flex-shrink-0" />
            {label}
          </Link>
        ))}

        {user?.is_admin && (
          <Link
            href="/admin"
            className={cn(
              "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
              pathname === "/admin"
                ? "bg-secondary/10 text-secondary font-medium"
                : "text-gray-500 hover:text-ink hover:bg-surface-hover"
            )}
          >
            <ShieldCheck className="h-4 w-4 flex-shrink-0" />
            Admin
          </Link>
        )}
      </nav>

      {/* Usuário logado */}
      {user && (
        <div className="px-5 py-3 border-t border-surface-border">
          <p className="text-xs text-ink truncate">{user.full_name}</p>
          <div className="flex items-center justify-between mt-1">
            <p className="text-[11px] text-gray-500 truncate">{user.email}</p>
            <button
              onClick={logout}
              className="flex items-center gap-1 text-[11px] text-gray-500 hover:text-red-600 transition-colors flex-shrink-0 ml-2"
              title="Sair"
            >
              <LogOut className="h-3 w-3" />
              Sair
            </button>
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="px-5 py-4 border-t border-surface-border">
        <p className="text-[11px] font-mono text-gray-500">EPUB3 Fixed Layout</p>
        <p className="text-[11px] font-mono text-gray-400">v1.0.0</p>
      </div>
    </aside>
  );
}
