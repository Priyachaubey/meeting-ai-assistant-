import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#101116",
        mist: "#f4f6f8",
        jade: "#2dd4bf",
        coral: "#ff6b5f",
        // Was a generic Tailwind violet-600 placeholder before there was a real logo.
        // Now set to the actual mid-tone purple sampled from the hexagon mark.
        iris: "#5B0A8C",
        // Brand ramp, extracted directly from the uploaded logo by sampling pixel clusters
        // (see brand/BRAND.md for the extraction method and exact source coordinates):
        //   brand.ink     — darkest, from the wordmark text
        //   brand.primary — mid-tone, the main hexagon/diamond fill (same value as `iris`)
        //   brand.accent  — brightest, the small highlight hexagon + gradient highlights
        brand: { ink: "#33005C", primary: "#5B0A8C", accent: "#8B1FC7" },
      },
      fontFamily: {
        display: ["var(--font-display)", "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        // Was teal (matched nothing brand-related) — now a brand-purple glow.
        glow: "0 24px 80px rgba(139, 31, 199, .28)",
        soft: "0 16px 48px rgba(16, 17, 22, .12)",
      },
      backgroundImage: {
        "brand-gradient": "linear-gradient(135deg, #33005C 0%, #5B0A8C 55%, #8B1FC7 100%)",
      },
    },
  },
  plugins: [],
};
export default config;
