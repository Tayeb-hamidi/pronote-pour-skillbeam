import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        panel: "#f5fbff",
        neonBlue: "#2563eb",
        neonViolet: "#0f766e",
        deepNavy: "#1f3b56"
      },
      boxShadow: {
        glow: "0 8px 24px rgba(37, 99, 235, 0.18)",
        violetGlow: "0 8px 28px rgba(15, 118, 110, 0.18)"
      },
      keyframes: {
        fadeInUp: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" }
        }
      },
      animation: {
        fadeInUp: "fadeInUp 420ms ease-out"
      }
    }
  },
  plugins: []
};

export default config;
