import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Paleta institucional PREDES (https://predes.org.pe/)
        mountain: {
          100: "#E5F4EE",
          500: "#5BBB5D",
          700: "#009257",
          800: "#1B7F4F",
          900: "#0B3B26",
        },
        earth: {
          200: "#F1DCC0",
          500: "#B8753C",
          700: "#7A4A28",
        },
        sky: {
          200: "#CCEAED",
          500: "#0095A4",
          700: "#007480",
        },
        level: {
          1: "#5BBB5D",
          2: "#EBB320",
          3: "#F57C15",
          4: "#970A00",
        },
        ink: {
          300: "#BDBDBD",
          600: "#555555",
          900: "#1A1A1A",
        },
        paper: "#FAFAF7",
        mock: "#F57C15",
      },
      fontFamily: {
        display: ["Metropolis", "system-ui", "sans-serif"],
        sans: ["Metropolis", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
} satisfies Config;
