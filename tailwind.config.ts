import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        borr: {
          navy: "#1E3A5F",
          blue: "#2563EB",
          green: "#065F46",
          amber: "#92400E",
        },
      },
    },
  },
  plugins: [],
};
export default config;
