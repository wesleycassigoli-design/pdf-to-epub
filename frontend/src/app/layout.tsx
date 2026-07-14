import type { Metadata } from "next";
import { Inter, Fraunces, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/layout/Providers";
import { Toaster } from "sonner";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

// Serifada editorial para títulos — dá personalidade de "livro/publicação"
// em vez de uma sans genérica em tudo.
const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  weight: ["500", "600"],
  style: ["normal", "italic"],
});

// Monoespaçada para dados técnicos: nome de arquivo, tamanho, progresso.
const jbmono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jbmono",
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "PDF → EPUB3 | Conversor de Livros",
  description: "Converta PDFs em EPUB3 Fixed Layout com fidelidade total à diagramação original",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={`${inter.variable} ${fraunces.variable} ${jbmono.variable}`}>
      <body className="bg-surface text-white antialiased min-h-screen font-sans">
        <Providers>
          {children}
          <Toaster
            theme="dark"
            position="bottom-right"
            toastOptions={{
              style: {
                background: "#12151c",
                border: "1px solid #1f2430",
                color: "#fff",
              },
            }}
          />
        </Providers>
      </body>
    </html>
  );
}
