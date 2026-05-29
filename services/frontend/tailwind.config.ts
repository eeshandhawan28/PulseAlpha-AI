import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./pages/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./app/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        display: ["'Syne'", "sans-serif"],
        body: ["'DM Sans'", "sans-serif"],
        mono: ["'JetBrains Mono'", "monospace"],
      },
      colors: {
        bg0: "#04060f",
        bg1: "#080c18",
        bg2: "#0d1222",
        bg3: "#111827",
        border: "#1a2540",
        "border-active": "#2a3d66",
        t1: "#e8edf5",
        t2: "#8896b0",
        t3: "#4a5876",
        amber: "#f59e0b",
        "amber-dim": "rgba(245,158,11,0.15)",
        ice: "#60a5fa",
        "ice-dim": "rgba(96,165,250,0.12)",
        emerald: "#34d399",
        "emerald-dim": "rgba(52,211,153,0.12)",
        rose: "#f87171",
        "rose-dim": "rgba(248,113,113,0.12)",
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};

export default config;
