"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { motion } from "framer-motion";

// Mixed loop of the 3 licensed video clips and 4 Ken Burns photo slides
// (see public/CREDITS.md for sources/licenses) -- alternating video/photo
// keeps the loop visually varied without needing more raw footage than
// was actually cleared for use. Mobile and prefers-reduced-motion each
// get a cheaper path (see below) rather than a scaled-down version of
// this one, since neither should ever pay for video decode at all.
type Slide =
  | { kind: "video"; id: string; mp4: string; webm: string; poster: string; duration: number }
  | { kind: "photo"; id: string; src: string; duration: number; zoom: "in" | "out" };

const SLIDES: Slide[] = [
  { kind: "video", id: "v4334", mp4: "/video/4334.mp4", webm: "/video/4334.webm", poster: "/video/4334-poster.jpg", duration: 7000 },
  { kind: "photo", id: "p1", src: "/img/hero-photo-1.jpg", duration: 9000, zoom: "in" },
  { kind: "video", id: "v4330", mp4: "/video/4330.mp4", webm: "/video/4330.webm", poster: "/video/4330-poster.jpg", duration: 7000 },
  { kind: "photo", id: "p2", src: "/img/hero-photo-2.jpg", duration: 9000, zoom: "out" },
  { kind: "video", id: "v24511", mp4: "/video/24511.mp4", webm: "/video/24511.webm", poster: "/video/24511-poster.jpg", duration: 7000 },
  { kind: "photo", id: "p3", src: "/img/hero-photo-3.jpg", duration: 9000, zoom: "in" },
  { kind: "photo", id: "p4", src: "/img/hero-photo-4.jpg", duration: 9000, zoom: "out" },
];

const MOBILE_SLIDES: Slide[] = SLIDES.filter((s): s is Extract<Slide, { kind: "photo" }> => s.kind === "photo");

const FIRST_POSTER = "/video/4334-poster.jpg";
const CROSSFADE_MS = 1500;

// useSyncExternalStore (not state+effect) so there's no setState-in-effect
// render cascade, and the server snapshot is a real, correct value rather
// than a placeholder that flips after mount.
function useMediaQuery(query: string): boolean {
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

function useMounted(): boolean {
  return useSyncExternalStore(
    () => () => {},
    () => true,
    () => false
  );
}

function PhotoSlide({ slide, active }: { slide: Extract<Slide, { kind: "photo" }>; active: boolean }) {
  const zoomIn = slide.zoom === "in";
  return (
    <motion.img
      src={slide.src}
      alt=""
      aria-hidden
      className="absolute inset-0 h-full w-full object-cover"
      initial={false}
      animate={active ? { scale: zoomIn ? [1, 1.12] : [1.12, 1] } : {}}
      transition={active ? { duration: slide.duration / 1000, ease: "linear" } : undefined}
      style={{ scale: zoomIn ? 1 : 1.12 }}
    />
  );
}

function VideoSlide({ slide, active }: { slide: Extract<Slide, { kind: "video" }>; active: boolean }) {
  const ref = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (active) {
      el.currentTime = 0;
      el.play().catch(() => {});
    } else {
      el.pause();
    }
  }, [active]);

  return (
    <video
      ref={ref}
      className="absolute inset-0 h-full w-full object-cover"
      muted
      playsInline
      loop
      preload={active ? "auto" : "none"}
      poster={slide.poster}
    >
      {active && (
        <>
          <source src={slide.webm} type="video/webm" />
          <source src={slide.mp4} type="video/mp4" />
        </>
      )}
    </video>
  );
}

// Full motion loop: mixed video+photo slides, crossfading, paused
// whenever the tab is hidden or the hero scrolls offscreen so it never
// burns battery/bandwidth for a background a visitor isn't looking at.
function MotionLoop({ slides }: { slides: Slide[] }) {
  const [index, setIndex] = useState(0);
  const [running, setRunning] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(([entry]) => setRunning(entry.isIntersecting), { threshold: 0.1 });
    observer.observe(el);
    const onVisibility = () => setRunning(!document.hidden && (el.getBoundingClientRect().bottom > 0));
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      observer.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  useEffect(() => {
    if (!running) return;
    const current = slides[index];
    const timer = setTimeout(() => setIndex((i) => (i + 1) % slides.length), current.duration);
    return () => clearTimeout(timer);
  }, [index, running, slides]);

  // Only the active slide and its immediate neighbor stay mounted, so a
  // 7-slide loop never has more than 2 videos decoding (or loaded) at once.
  const nextIndex = (index + 1) % slides.length;

  return (
    <div ref={containerRef} className="absolute inset-0 overflow-hidden">
      {slides.map((slide, i) => {
        const active = i === index;
        const shouldMount = i === index || i === nextIndex;
        if (!shouldMount) return null;
        return (
          <div
            key={slide.id}
            className="absolute inset-0 transition-opacity ease-linear"
            style={{ opacity: active ? 1 : 0, transitionDuration: `${CROSSFADE_MS}ms` }}
          >
            {slide.kind === "video" ? (
              <VideoSlide slide={slide} active={active && running} />
            ) : (
              <PhotoSlide slide={slide} active={active && running} />
            )}
          </div>
        );
      })}
    </div>
  );
}

export function HeroMedia() {
  const mounted = useMounted();
  const isMobile = useMediaQuery("(max-width: 639px)");
  const prefersReducedMotion = useMediaQuery("(prefers-reduced-motion: reduce)");

  return (
    <div className="absolute inset-0 -z-10">
      {/* Static poster -- the only thing rendered at first paint/SSR, and
          the permanent fallback for prefers-reduced-motion. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={FIRST_POSTER} alt="" aria-hidden className="absolute inset-0 h-full w-full object-cover" />

      {mounted && !prefersReducedMotion && <MotionLoop slides={isMobile ? MOBILE_SLIDES : SLIDES} />}

      {/* Navy wash -- strong enough that headline/body text stays WCAG
          AA-readable regardless of what's playing underneath. */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "linear-gradient(115deg, rgba(5,10,52,0.88) 0%, rgba(5,10,52,0.8) 35%, rgba(5,10,52,0.6) 65%, rgba(5,10,52,0.75) 100%)",
        }}
      />
      <div className="absolute inset-0 bg-gradient-to-t from-bg via-transparent to-bg/40" />
    </div>
  );
}
