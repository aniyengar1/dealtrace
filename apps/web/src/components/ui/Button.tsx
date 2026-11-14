import Link from "next/link";
import type { AnchorHTMLAttributes, ButtonHTMLAttributes } from "react";

const BASE =
  "inline-flex items-center justify-center gap-1.5 rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold disabled:opacity-50 disabled:pointer-events-none px-3.5 py-2";

const VARIANTS = {
  primary: "bg-gold text-gold-ink hover:bg-gold/90",
  secondary: "border border-border-strong text-ink hover:bg-surface-raised",
  ghost: "text-ink-muted hover:text-ink",
};

type Variant = keyof typeof VARIANTS;

export function Button({
  variant = "secondary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return <button className={`${BASE} ${VARIANTS[variant]} ${className}`} {...props} />;
}

export function LinkButton({
  variant = "secondary",
  className = "",
  href,
  ...props
}: AnchorHTMLAttributes<HTMLAnchorElement> & { variant?: Variant; href: string }) {
  return <Link href={href} className={`${BASE} ${VARIANTS[variant]} ${className}`} {...props} />;
}
