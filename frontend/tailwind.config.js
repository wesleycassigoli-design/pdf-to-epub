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
        brand: {
          400: "#6690ff",
          500: "#3d6eff",
          600: "#2050f5",
        },
        surface: {
          DEFAULT: "#0f1117",
          card: "#181c27",
          border: "#252a38",
          hover: "#1e2336",
        },
      },
    },
  },
  plugins: [],
};
