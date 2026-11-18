import Link from "next/link";
import type { SortKey } from "@/lib/dealLabels";

export function SortableHeader({
  sortKey,
  label,
  currentSort,
  currentDir,
  searchParams,
  align = "left",
}: {
  sortKey: SortKey;
  label: string;
  currentSort: SortKey;
  currentDir: "asc" | "desc";
  searchParams: Record<string, string | undefined>;
  align?: "left" | "right";
}) {
  const isActive = currentSort === sortKey;
  const nextDir = isActive && currentDir === "desc" ? "asc" : "desc";
  const params = new URLSearchParams(
    Object.entries(searchParams).filter(([, v]) => v !== undefined) as [string, string][]
  );
  params.set("sort", sortKey);
  params.set("dir", nextDir);
  params.delete("page");

  return (
    <Link
      href={`/deals?${params.toString()}`}
      className={`inline-flex items-center gap-1 hover:text-ink ${isActive ? "text-ink" : ""} ${align === "right" ? "justify-end" : ""}`}
    >
      {label}
      {isActive && <span className="text-accent">{currentDir === "desc" ? "↓" : "↑"}</span>}
    </Link>
  );
}
