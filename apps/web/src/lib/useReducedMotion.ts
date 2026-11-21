"use client";

import { useCallback, useSyncExternalStore } from "react";

// useSyncExternalStore (not state+effect) so there's no setState-in-effect
// render cascade and the server snapshot is a real, correct value (the
// conservative "full motion, desktop-width" default) rather than a
// placeholder that flips after mount. The global CSS override in
// globals.css only collapses *CSS* animation/transition durations; it
// can't reach a JS-driven value (framer-motion's `animate()`, a
// RAF-driven counter, etc.), so any component animating a number or a
// hand-rolled motion value has to check this explicitly.
export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      const mql = window.matchMedia(query);
      mql.addEventListener("change", onChange);
      return () => mql.removeEventListener("change", onChange);
    },
    [query]
  );
  const getSnapshot = useCallback(() => window.matchMedia(query).matches, [query]);
  const getServerSnapshot = useCallback(() => false, []);
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

export function usePrefersReducedMotion(): boolean {
  return useMediaQuery("(prefers-reduced-motion: reduce)");
}

// Tailwind's `sm` breakpoint (640px) -- below it, a count-up animation
// reads as a distracting flicker on a small screen rather than a nice
// flourish, so narrow viewports skip it the same way reduced-motion does.
export function useNarrowViewport(): boolean {
  return useMediaQuery("(max-width: 639px)");
}
