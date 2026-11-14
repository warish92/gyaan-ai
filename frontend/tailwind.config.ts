import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        gyaan: {
          primary: "#2563EB",
          primaryHover: "#1D4ED8",
          text: "#172033",
          textSecondary: "#64748B",
          background: "#F7F9FC",
          surface: "#FFFFFF",
          softBlue: "#EFF6FF",
          border: "#E2E8F0",
          success: "#16A34A",
          warning: "#F59E0B",
          error: "#DC2626",
          ai: "#7C5CFC",
          teal: "#0F9F9A",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "Inter", "system-ui", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
