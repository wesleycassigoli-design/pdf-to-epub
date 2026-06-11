import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/layout/Providers";
import { Toaster } from "sonner";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "PDF → EPUB3 | Conversor de Livros",
  description: "Converta PDFs em EPUB3 Fixed Layout com fidelidade total à diagramação original",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={inter.variable}>
      <body className="bg-surface text-white antialiased min-h-screen">
        <Providers>
          {children}
          <Toaster
            theme="dark"
            position="bottom-right"
            toastOptions={{
              style: {
                background: "#181c27",
                border: "1px solid #252a38",
                color: "#fff",
              },
            }}
          />
        </Providers>
      </body>
    </html>
  );
}
