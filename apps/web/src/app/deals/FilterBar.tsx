"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { PRICE_BUCKET_LABELS, CONSIDERATION_TYPE_LABELS } from "@/lib/dealLabels";

function Select({
  value,
  onChange,
  options,
  allLabel,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  allLabel: string;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
    >
      <option value="">{allLabel}</option>
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

export function FilterBar({ years }: { years: string[] }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [q, setQ] = useState(searchParams.get("q") ?? "");

  function updateParam(key: string, value: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (value) params.set(key, value);
    else params.delete(key);
    params.delete("page");
    router.push(`/deals?${params.toString()}`);
  }

  function onSubmitSearch(e: React.FormEvent) {
    e.preventDefault();
    updateParam("q", q);
  }

  return (
    <div className="flex flex-wrap items-center gap-2.5">
      <form onSubmit={onSubmitSearch} className="flex-1 min-w-[200px]">
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search target or acquirer…"
          className="w-full rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-ink placeholder:text-ink-faint focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        />
      </form>
      <Select
        value={searchParams.get("year") ?? ""}
        onChange={(v) => updateParam("year", v)}
        allLabel="All years"
        options={years.map((y) => ({ value: y, label: y }))}
      />
      <Select
        value={searchParams.get("consideration") ?? ""}
        onChange={(v) => updateParam("consideration", v)}
        allLabel="All consideration"
        options={Object.entries(CONSIDERATION_TYPE_LABELS).map(([value, label]) => ({ value, label }))}
      />
      <Select
        value={searchParams.get("price") ?? ""}
        onChange={(v) => updateParam("price", v)}
        allLabel="All price ranges"
        options={Object.entries(PRICE_BUCKET_LABELS).map(([value, label]) => ({ value, label }))}
      />
    </div>
  );
}
