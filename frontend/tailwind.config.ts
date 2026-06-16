import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#17202a",
        mist: "#f5f7fb",
        line: "#dbe3ec",
        pine: "#1f6f5b",
        amber: "#b26b1f",
        berry: "#a33b5f",
        cyan: "#277c91"
      },
      boxShadow: {
        soft: "0 16px 50px rgba(23, 32, 42, 0.10)"
      }
    }
  },
  plugins: []
};

export default config;
