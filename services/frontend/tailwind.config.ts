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
        display: ["'Cormorant Garamond'", "serif"],
        body: ["'Jost'", "sans-serif"],
        mono: ["'Spline Sans Mono'", "monospace"],
      },
      colors: {
        // Warm obsidian scale
        bg0: "#0b0a08",
        bg1: "#11100d",
        bg2: "#171511",
        bg3: "#1e1b16",
        // Hairlines
        border: "#2a2519",
        "border-active": "#4a3f29",
        // Ivory text scale
        t1: "#ede8dc",
        t2: "#a39a86",
        t3: "#5f5747",
        // Champagne gold
        gold: "#c9a96a",
        "gold-bright": "#e8cf9e",
        "gold-dim": "rgba(201,169,106,0.10)",
        // Jade (bullish)
        jade: "#8fc8a8",
        "jade-dim": "rgba(143,200,168,0.10)",
        // Muted blood (bearish)
        blood: "#d28a7c",
        "blood-dim": "rgba(210,138,124,0.10)",
        // Platinum (informational)
        plat: "#a9bdd4",
        "plat-dim": "rgba(169,189,212,0.10)",
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};

export default config;
