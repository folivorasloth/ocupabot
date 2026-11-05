import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        marca: { 50: "#eefbf6", 100: "#d5f5e8", 500: "#16a37b", 600: "#0f8a67", 700: "#0d6e53", 900: "#0b3d30" },
      },
    },
  },
  plugins: [],
} satisfies Config;
