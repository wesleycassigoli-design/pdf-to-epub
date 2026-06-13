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
        "brand-400": "#6690ff",
        "brand-500": "#3d6eff",
        "brand-600": "#2050f5",
        "surface": "#0f1117",
        "surface-card": "#181c27",
        "surface-border": "#252a38",
        "surface-hover": "#1e2336",
      },
    },
  },
  plugins: [],
};
