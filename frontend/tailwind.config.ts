import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        ink: "#18222f",
        paper: "#f6f1e8",
        clay: "#cc7a43",
        moss: "#4d6a5d",
        mist: "#d9d2c3"
      }
    }
  },
  plugins: []
};

export default config;
