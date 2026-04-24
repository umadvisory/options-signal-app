import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/data/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        ink: "#111827",
        muted: "#687389",
        panel: "#ffffff",
        line: "#dfe6f0",
        soft: "#f6f8fb",
        brand: "#2563eb",
        success: "#059669",
        warning: "#f59e0b",
        danger: "#dc2626"
      },
      boxShadow: {
        card: "0 18px 50px rgba(15, 23, 42, 0.08)",
        soft: "0 10px 28px rgba(15, 23, 42, 0.05)"
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"]
      }
    }
  },
  plugins: []
};

export default config;
