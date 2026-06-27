# Microtechnique AI Meeting — Brand Assets

Source: `source/logo-original.jpeg`, uploaded 2026-06-26. Everything in this
folder and in `apps/web/public/brand/` + `apps/web/public/pwa/` was generated
mechanically from that file (Pillow + numpy pixel sampling, ImageMagick where
noted) — nothing here is an invented or AI-generated stand-in for the real
logo.

## Color extraction (how, not just what)

The logo's background is near-flat white (`rgb(254,254,254)` sampled at all
four corners), so foreground pixels were isolated by distance-from-white,
then clustered to find dominant colors:

| Token | Hex | Sampled from |
|---|---|---|
| `brand.ink` | `#33005C` | Darkest 1% of foreground pixels in the wordmark text region (y 700–1010 of the 1254px source) — the true text "ink" color, excluding anti-aliased edge blending with the white background. |
| `brand.primary` (= `iris`) | `#5B0A8C` | Average of the two large diagonal hexagon shapes' mid-tone fill (sampled at their visual centers). |
| `brand.accent` | `#8B1FC7` | Average of the small bright hexagon (bottom-left of the mark) — the lightest, most saturated point in the gradient. |

These three form an actual gradient ramp in the source logo (dark → mid →
bright), which is why `brand-gradient` in Tailwind uses them as literal
gradient stops rather than arbitrary picks.

**Not derivable from the logo, chosen separately:** `jade` (success),
`coral` (error) — the logo is monochromatic purple, it has no green or red to
extract. These are unchanged from before and are standard accessible
enterprise-SaaS semantic colors, not brand colors. Said outright here so
nobody mistakes them for "from the logo."

## Typography

Logo wordmark uses a geometric, slightly industrial display face (flat
terminals, angular cuts). Rather than guess at the exact font, paired it with
**Space Grotesk** for headings (via `next/font/google`, `--font-display` CSS
variable, applied to `h1`/`h2`/`h3` by default) — it's in the same geometric
register as the logo, keeps body text on **Inter** for readability, and
matches the Space Grotesk + Inter pairing already used across your other
Microtechnique IT products (portfolio site, travel app), so this product
doesn't look unrelated to the rest of your work.

## What's wired into the real app (`apps/web`)

- `tailwind.config.ts` — `iris` changed from a generic Tailwind violet-600
  placeholder (`#7c3aed`, never brand-derived) to the real `#5B0A8C`. Added
  `brand.ink/primary/accent` tokens and a `brand-gradient` background image
  utility. Retinted `shadow-glow` from teal to brand purple — it was never
  matched to anything before.
- `components/button.tsx` — primary button background changed from neutral
  `bg-ink` to `bg-brand-gradient`. Secondary/danger button variants (pages
  that pass `className="bg-white text-ink"` or `"bg-coral"`) are untouched —
  `tailwind-merge` resolves those overrides correctly regardless of the new
  default.
- Logo image (`icon-mark.png`) replaces the "CP"/"M" text-square placeholder
  in: landing page nav, sidebar (`app-shell.tsx`), login page.
- `layout.tsx` — real favicon, apple-touch-icon, Open Graph image, theme
  color, and `manifest.json` (couldn't exist before — it would've had to
  reference icon files that didn't exist yet).
- `globals.css` — Space Grotesk on headings, selection-highlight color
  retinted to brand purple.

**Not touched:** card backgrounds, chart colors, spacing/animation tokens.
The codebase doesn't have a reusable Card component or a wired charts page
yet (analytics page is still on the deferred list from `AUDIT.md` §6) — adding
a "card design system" or "chart palette" for components that don't exist in
a working form yet would be the same fabrication problem as everything else
in this project's history. Once analytics is wired for real, it should use
`brand.primary`/`brand.accent` for series colors — noted here so that's not
forgotten, not implemented speculatively now.

## File map

```
apps/web/public/brand/        — used by the live web app
  logo-transparent.png/.webp  — full lockup (mark + wordmark), light backgrounds
  logo-dark-theme.png/.webp   — same lockup, wordmark recolored white for dark backgrounds
  logo-mono-black.png         — single-color black, transparent bg
  logo-mono-white.png         — single-color white, transparent bg
  icon-mark.png/.webp/.svg    — mark only, no wordmark (square, for icons/avatars)
  og-image.png                — 1200×630 Open Graph card

apps/web/public/pwa/          — manifest icons (192/512, + maskable variants with safe-zone padding)
apps/web/public/favicon.ico   — multi-size (16/32/48)
apps/web/public/apple-touch-icon.png

brand/source/                 — the original upload + every generated variant, full resolution
brand/android/                — mipmap-*dpi launcher icons + adaptive foreground/background layers
brand/ios/                    — AppIcon set (20pt–1024pt)
brand/desktop/                — icon.ico (Windows), icon.icns (macOS), icon-256-linux.png
```

## Honest limitations

- **`icon-mark.svg` is not a true vector.** No vector source file (e.g. the
  original Illustrator/Figma file) or vectorization tool (potrace etc.) was
  available in this sandbox — it's the raster PNG base64-embedded in an SVG
  wrapper, which is a valid SVG file (renders fine, usable wherever a `.svg`
  extension is required) but gets none of a real vector's benefits: it won't
  stay crisp scaled up arbitrarily, and the file is *larger* than the PNG,
  not smaller. For large-format use (signage, print, a billboard), get the
  real vector source from whoever designed the logo, or run it through
  proper vectorization software.
- **`.icns` was generated successfully** via Pillow — confirmed it actually
  wrote a valid multi-resolution file, not just attempted to. Still not
  tested on an actual Mac, since this sandbox doesn't have one.
- **Android/iOS/desktop icons have no project to live in yet.** They're
  correctly sized and organized so they drop straight into a real
  `android/app/src/main/res/`, `ios/.../Assets.xcassets/`, or Electron
  `build/icons/` folder the moment those projects exist — generating them now
  doesn't create the mobile/desktop apps themselves.
