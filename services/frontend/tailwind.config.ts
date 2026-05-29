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
      colors: {
        background: "#0a0e1a",
        surface: "#0f1629",
        border: "#1e2d4a",
        muted: "#64748b",
        "muted-foreground": "#94a3b8",
      },
    },
  },
  plugins: [],
};

export default config;
