import type { Metadata } from "next";
import { JetBrains_Mono } from "next/font/google";
import localFont from "next/font/local";
import "./globals.css";
import { Providers } from "@/components/layout/Providers";
import { Toaster } from "sonner";

// Fonte de marca Afya (mesma família usada nos EPUBs gerados) — cobre sans e display.
const afyaSans = localFont({
  variable: "--font-afyasans",
  src: [
    { path: "../fonts/AfyaSans/AfyaSans-Light.ttf", weight: "300", style: "normal" },
    { path: "../fonts/AfyaSans/AfyaSans-LightItalic.ttf", weight: "300", style: "italic" },
    { path: "../fonts/AfyaSans/AfyaSans-Regular.ttf", weight: "400", style: "normal" },
    { path: "../fonts/AfyaSans/AfyaSans-Italic.ttf", weight: "400", style: "italic" },
    { path: "../fonts/AfyaSans/AfyaSans-Bold.ttf", weight: "700", style: "normal" },
    { path: "../fonts/AfyaSans/AfyaSans-BoldItalic.ttf", weight: "700", style: "italic" },
    { path: "../fonts/AfyaSans/AfyaSans-ExtraBold.ttf", weight: "800", style: "normal" },
    { path: "../fonts/AfyaSans/AfyaSans-ExtraBoldItalic.ttf", weight: "800", style: "italic" },
  ],
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
  icons: { icon: "/logo-afya.svg" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={`${afyaSans.variable} ${jbmono.variable}`}>
      <body className="bg-surface text-ink antialiased min-h-screen font-sans">
        <Providers>
          {children}
          <Toaster
            theme="light"
            position="bottom-right"
            toastOptions={{
              style: {
                background: "#ffffff",
                border: "1px solid #DDDBDD",
                color: "#333333",
              },
            }}
          />
        </Providers>
      </body>
    </html>
  );
}
