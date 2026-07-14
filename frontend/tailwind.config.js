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
        // Dourado/latão — remete a marcação de página e lombada de livro,
        // evita o azul genérico de SaaS.
        "brand-400": "#e3bd7e",
        "brand-500": "#c99a4f",
        "brand-600": "#a67c35",
        // Grafite com leve matiz azulado (não preto puro) — mais sofisticado
        // do que #000/#0f1117 chapado.
        "surface": "#0b0d12",
        "surface-card": "#12151c",
        "surface-border": "#1f2430",
        "surface-hover": "#191d27",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        display: ["var(--font-fraunces)", "Georgia", "serif"],
        mono: ["var(--font-jbmono)", "monospace"],
      },
    },
  },
  plugins: [],
};
