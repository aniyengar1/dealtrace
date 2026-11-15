"use client";

import { useEffect, useRef, useState } from "react";
import { useInView, animate } from "framer-motion";

export function StatNumber({
  value,
  label,
  n,
  size = "md",
  prefix = "",
  suffix = "",
  decimals = 0,
}: {
  value: number;
  label: string;
  n?: number;
  size?: "md" | "lg";
  prefix?: string;
  suffix?: string;
  decimals?: number;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.6 });
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    if (!inView) return;
    const controls = animate(0, value, {
      duration: 1.1,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: setDisplay,
    });
    return () => controls.stop();
  }, [inView, value]);

  return (
    <div className="rounded-lg bg-bg/55 px-4 py-3 backdrop-blur-sm">
      <span
        ref={ref}
        className={`font-serif tabular-nums text-accent ${size === "lg" ? "text-4xl sm:text-5xl" : "text-3xl"}`}
      >
        {prefix}
        {display.toFixed(decimals)}
        {suffix}
      </span>
      <p className="mt-1.5 text-sm text-ink-muted">
        {label}
        {n !== undefined && <span className="text-ink-faint"> (n = {n})</span>}
      </p>
    </div>
  );
}
