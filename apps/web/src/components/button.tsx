import * as React from "react";
import { cn } from "@/lib/utils";

// Extended in the Phase 4/5 merge with variant/size/loading — the new meeting-room.tsx and
// search/page.tsx components need them (e.g. <Button variant="secondary" size="sm" loading>).
// Deliberately built from the *existing* brand tokens in tailwind.config.ts (ink/jade/coral/
// brand-gradient) rather than the new design-system CSS variables that came with this same
// upstream change, so the rest of the app's look stays exactly as it was — see the merge
// report for why that bigger visual overhaul was left out of this pass. `variant="primary"`
// + `size="md"` (the defaults) render identically to the single style this component used
// to have, so every existing call site (`<Button onClick={...}>Text</Button>`) is unaffected.

type Variant = "primary" | "secondary" | "ghost" | "danger" | "success";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

const variants: Record<Variant, string> = {
  primary: "border border-ink/10 bg-brand-gradient text-white shadow-soft hover:-translate-y-0.5 hover:brightness-110",
  secondary: "border border-ink/10 bg-white text-ink shadow-soft hover:bg-mist",
  ghost: "text-ink/70 hover:bg-ink/5 hover:text-ink",
  danger: "border border-ink/10 bg-coral text-white hover:brightness-110 shadow-soft",
  success: "border border-ink/10 bg-jade text-white hover:brightness-110 shadow-soft",
};

const sizes: Record<Size, string> = {
  sm: "h-8 px-3 text-xs gap-1.5 rounded-md",
  md: "h-10 px-4 text-sm gap-2 rounded-md",
  lg: "h-12 px-6 text-base gap-2.5 rounded-lg",
};

export function Button({
  className,
  variant = "primary",
  size = "md",
  loading = false,
  disabled,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center font-medium transition disabled:cursor-not-allowed disabled:opacity-60",
        variants[variant],
        sizes[size],
        className
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading && (
        <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      )}
      {children}
    </button>
  );
}
