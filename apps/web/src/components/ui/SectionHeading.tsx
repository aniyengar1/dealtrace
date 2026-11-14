import type { ReactNode } from "react";

export function SectionHeading({
  eyebrow,
  title,
  description,
}: {
  eyebrow?: string;
  title: ReactNode;
  description?: ReactNode;
}) {
  return (
    <div className="max-w-2xl">
      {eyebrow && <p className="text-xs font-medium uppercase tracking-[0.14em] text-gold">{eyebrow}</p>}
      <h2 className="mt-2 font-serif text-3xl font-semibold tracking-tight text-ink sm:text-4xl">{title}</h2>
      {description && <p className="mt-3 text-base text-ink-muted">{description}</p>}
    </div>
  );
}
