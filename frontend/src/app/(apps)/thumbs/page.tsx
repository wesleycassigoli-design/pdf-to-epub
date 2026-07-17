"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";

// Os geradores em si (public/thumbs/selecao.html, marcas.html,
// posgraduacao.html) são HTML estático servido pelo Next.js, embutido aqui
// via iframe. LIMITAÇÃO CONHECIDA E ACEITA NESTA FASE: por serem arquivos
// estáticos, continuam acessíveis por URL direta (ex: /thumbs/marcas.html)
// sem passar pelo guard de autenticação desta página React — só o link
// /thumbs (esta página) é protegido. Numa fase 2, se precisar de proteção
// real por arquivo, portar os geradores pra páginas React.
export default function ThumbsPage() {
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
      <iframe
        src="/thumbs/selecao.html"
        className="flex-1 w-full border-0"
        title="Gerador de Thumbs"
      />
    </div>
  );
}
