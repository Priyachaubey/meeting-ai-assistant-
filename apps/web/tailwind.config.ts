import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#101116",
          secondary: "#52525b",
          tertiary: "#8b8b96",
          placeholder: "#b4b4bd",
        },
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
        //   brand.DEFAULT — added in the Phase 4/5 merge so `text-brand`/`border-brand`
        //                   (used by the new search/meeting-room components) resolve to
        //                   the same purple as `primary`, instead of to nothing.
        brand: { DEFAULT: "#5B0A8C", ink: "#33005C", primary: "#5B0A8C", accent: "#8B1FC7" },
        // Added in the Phase 4/5 merge for the new meeting-room/search UI. Neutral
        // surface tokens — not a new palette, just named layers of the existing white/
        // near-white card backgrounds those two components expect.
        surface: {
          DEFAULT: "#ffffff",
          hover: "#f6f7f9",
          active: "#eef0f4",
          border: "rgba(16,17,22,.08)",
        },
        elevated: "#ffffff",
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
