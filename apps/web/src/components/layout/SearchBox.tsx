"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function SearchBox() {
  const router = useRouter();
  const [value, setValue] = useState("");

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = value.trim();
    router.push(q ? `/deals?q=${encodeURIComponent(q)}` : "/deals");
  }

  return (
    <form onSubmit={onSubmit} role="search">
      <label htmlFor="global-search" className="sr-only">
        Search deals
      </label>
      <input
        id="global-search"
        type="search"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Search deals…"
        className="w-full rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-ink placeholder:text-ink-faint focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold"
      />
    </form>
  );
}
