import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        mountain: {
          100: "#E6F0EA",
          500: "#6BA585",
          700: "#3A6B53",
          900: "#1F3A2E",
        },
        earth: {
          200: "#F1DCC0",
          500: "#B8753C",
          700: "#7A4A28",
        },
        sky: {
          200: "#CFE4F2",
          500: "#3E92CC",
          700: "#1F5F8A",
        },
        level: {
          1: "#4CAF50",
          2: "#FFC107",
          3: "#FF7043",
          4: "#D32F2F",
        },
        ink: {
          300: "#BDBDBD",
          600: "#555555",
          900: "#1A1A1A",
        },
        paper: "#FAFAF7",
        mock: "#F97316",
      },
      fontFamily: {
        display: ["'Plus Jakarta Sans'", "system-ui", "sans-serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
} satisfies Config;
