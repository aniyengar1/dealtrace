export function StatNumber({
  value,
  label,
  n,
  size = "md",
}: {
  value: string;
  label: string;
  n?: number;
  size?: "md" | "lg";
}) {
  return (
    <div>
      <div
        className={`font-serif tabular-nums text-gold ${size === "lg" ? "text-4xl sm:text-5xl" : "text-3xl"}`}
      >
        {value}
      </div>
      <p className="mt-1.5 text-sm text-ink-muted">
        {label}
        {n !== undefined && <span className="text-ink-faint"> (n = {n})</span>}
      </p>
    </div>
  );
}
