"use client";

import { useCallback, useSyncExternalStore } from "react";

// useSyncExternalStore (not state+effect) so there's no setState-in-effect
// render cascade and the server snapshot is a real, correct value (false
// -- full motion) rather than a placeholder that flips after mount. The
// global CSS override in globals.css only collapses *CSS* animation/
// transition durations; it can't reach a JS-driven value (framer-motion's
// `animate()`, a RAF-driven counter, etc.), so any component animating a
// number or a hand-rolled motion value has to check this explicitly.
export function usePrefersReducedMotion(): boolean {
  const subscribe = useCallback((onChange: () => void) => {
    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);
  const getSnapshot = useCallback(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches, []);
  const getServerSnapshot = useCallback(() => false, []);
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
