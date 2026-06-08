/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0f0f1a",
        card: "#1a1a2e",
        "card-hover": "#22223a",
        border: "#2a2a3e",
        accent: "#ff4655",
        "accent-dark": "#cc3444",
        cyan: "#00d4ff",
        "cyan-dark": "#00a8cc",
      },
      fontFamily: {
        sans: ["Inter", "sans-serif"],
      },
    },
  },
  plugins: [],
};
