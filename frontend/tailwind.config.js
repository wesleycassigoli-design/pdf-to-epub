/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Paleta oficial Afya (educacaomedica.afya.com.br) — mesmo rosa já usado
        // no CSS de marca dos EPUBs gerados.
        "brand-400": "#E26B94",
        "brand-500": "#D31C5B",
        "brand-600": "#A91649",
        "secondary": "#001d42",
        "ink": "#333333",
        "ink-border": "#DDDBDD",
        "paper": "#fbf9fd",
        // Tema claro — fundo off-white oficial da Afya, cards brancos,
        // bordas e hover num cinza claro derivado da mesma paleta.
        "surface": "#fbf9fd",
        "surface-card": "#ffffff",
        "surface-border": "#DDDBDD",
        "surface-hover": "#F3F1F6",
      },
      fontFamily: {
        sans: ["var(--font-afyasans)", "system-ui", "sans-serif"],
        display: ["var(--font-afyasans)", "system-ui", "sans-serif"],
        mono: ["var(--font-jbmono)", "monospace"],
      },
    },
  },
  plugins: [],
};
