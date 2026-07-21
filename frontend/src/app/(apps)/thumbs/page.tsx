"use client";

import Link from "next/link";
import { ArrowLeft, ShieldAlert } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

// Os geradores em si (public/thumbs/selecao.html, marcas.html,
// posgraduacao.html) são HTML estático servido pelo Next.js, embutido aqui
// via iframe. LIMITAÇÃO CONHECIDA E ACEITA NESTA FASE: por serem arquivos
// estáticos, continuam acessíveis por URL direta (ex: /thumbs/marcas.html)
// sem passar pelo guard desta página React OU pela checagem de app_access
// abaixo — só a rota /thumbs em si é protegida. Numa fase futura, se
// precisar de proteção real por arquivo, portar os geradores pra páginas
// React (servidas via alguma rota autenticada).
export default function ThumbsPage() {
  const { user } = useAuth();
  const hasAccess = !!user?.is_admin || !!user?.app_access?.includes("thumbs");

  return (
    <div className="min-h-screen flex flex-col bg-surface">
      <header className="flex items-center gap-2 px-4 py-3 border-b border-surface-border bg-surface-card">
        <Link
          href="/apps"
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-ink transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Aplicativos
        </Link>
      </header>

      {hasAccess ? (
        <iframe
          src="/thumbs/selecao.html"
          className="flex-1 w-full border-0"
          title="Gerador de Thumbs"
        />
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center gap-2 text-center px-4">
          <ShieldAlert className="h-8 w-8 text-red-500" />
          <p className="text-sm font-medium text-ink">Você não tem acesso a este aplicativo</p>
          <p className="text-xs text-gray-500">Peça a um administrador pra liberar o acesso ao Gerador de Thumbs.</p>
        </div>
      )}
    </div>
  );
}
