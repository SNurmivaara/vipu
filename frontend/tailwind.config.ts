import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  safelist: [
    // Balance colors - always include these
    "text-emerald-700",
    "text-emerald-400",
    "text-orange-600",
    "text-orange-400",
    "text-red-600",
    "text-red-400",
    "dark:text-emerald-400",
    "dark:text-orange-400",
    "dark:text-red-400",
  ],
  theme: {
    extend: {
      colors: {
        balance: {
          positive: "#22c55e",
          warning: "#eab308",
          negative: "#ef4444",
        },
      },
    },
  },
  plugins: [],
};

export default config;
