"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { motion } from "framer-motion";

// Mixed loop of the 3 licensed video clips and 8 Ken Burns photo slides
// (see public/CREDITS.md for sources/licenses) -- alternating night
// skyline footage with boardroom interiors and Manhattan/Central Park
// stills keeps the loop visually varied without needing more raw
// footage than was actually cleared for use. Mobile and
// prefers-reduced-motion each get a cheaper path (see below) rather
// than a scaled-down version of this one, since neither should ever pay
// for video decode at all.
//
// Rendered `absolute inset-0`, scoped to whichever `relative`
// ancestor mounts it (the home hero section, and nowhere else) --
// content below the hero is near-black with no imagery, per the
// site's Linear/Stripe-inspired direction. A much heavier dark wash
// than earlier rounds keeps the montage reading as a slow, subtle
// background (~20% visible) rather than a bright photo the headline
// competes with.
type Slide =
  | { kind: "video"; id: string; mp4: string; webm: string; poster: string; duration: number }
  | { kind: "photo"; id: string; src: string; duration: number; zoom: "in" | "out" };

const SLIDES: Slide[] = [
  { kind: "video", id: "v4334", mp4: "/video/4334.mp4", webm: "/video/4334.webm", poster: "/video/4334-poster.jpg", duration: 7000 },
  { kind: "photo", id: "p5", src: "/img/hero-photo-5.jpg", duration: 9000, zoom: "in" },
  { kind: "photo", id: "p1", src: "/img/hero-photo-1.jpg", duration: 9000, zoom: "out" },
  { kind: "video", id: "v4330", mp4: "/video/4330.mp4", webm: "/video/4330.webm", poster: "/video/4330-poster.jpg", duration: 7000 },
  { kind: "photo", id: "p6", src: "/img/hero-photo-6.jpg", duration: 9000, zoom: "in" },
  { kind: "photo", id: "p2", src: "/img/hero-photo-2.jpg", duration: 9000, zoom: "out" },
  { kind: "video", id: "v24511", mp4: "/video/24511.mp4", webm: "/video/24511.webm", poster: "/video/24511-poster.jpg", duration: 7000 },
  { kind: "photo", id: "p7", src: "/img/hero-photo-7.jpg", duration: 9000, zoom: "in" },
  { kind: "photo", id: "p8", src: "/img/hero-photo-8.jpg", duration: 9000, zoom: "out" },
  { kind: "photo", id: "p3", src: "/img/hero-photo-3.jpg", duration: 9000, zoom: "in" },
  { kind: "photo", id: "p4", src: "/img/hero-photo-4.jpg", duration: 9000, zoom: "out" },
];

const MOBILE_SLIDES: Slide[] = SLIDES.filter((s): s is Extract<Slide, { kind: "photo" }> => s.kind === "photo");

const FIRST_POSTER = "/video/4334-poster.jpg";
const CROSSFADE_MS = 1500;

// Mild brightness/contrast lift on the raw footage/photos themselves --
// applied to the media layer only, never the overlay or any text, so
// brightening the montage never touches how crisp the headline reads.
const MEDIA_FILTER = "brightness(0.9) contrast(1.05)";

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

function usePageVisible(): boolean {
  const subscribe = useCallback((onChange: () => void) => {
    document.addEventListener("visibilitychange", onChange);
    return () => document.removeEventListener("visibilitychange", onChange);
  }, []);
  const getSnapshot = useCallback(() => !document.hidden, []);
  const getServerSnapshot = useCallback(() => true, []);
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
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
      style={{ scale: zoomIn ? 1 : 1.12, filter: MEDIA_FILTER }}
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
      style={{ filter: MEDIA_FILTER }}
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
// whenever the tab is hidden so it never burns battery/bandwidth in a
// background tab. It no longer pauses on scroll -- being `fixed` means
// it's always the thing visible behind whatever's on screen, so "off
// screen" no longer applies the way it did when it was hero-only.
function MotionLoop({ slides }: { slides: Slide[] }) {
  const [index, setIndex] = useState(0);
  const running = usePageVisible();

  useEffect(() => {
    if (!running) return;
    const current = slides[index];
    const timer = setTimeout(() => setIndex((i) => (i + 1) % slides.length), current.duration);
    return () => clearTimeout(timer);
  }, [index, running, slides]);

  // Only the active slide and its immediate neighbor stay mounted, so an
  // 11-slide loop never has more than 2 videos/photos decoding at once.
  const nextIndex = (index + 1) % slides.length;

  return (
    <div className="absolute inset-0 overflow-hidden">
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
    <div className="absolute inset-0 -z-10 overflow-hidden">
      {/* Static poster -- the only thing rendered at first paint/SSR, and
          the permanent fallback for prefers-reduced-motion. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={FIRST_POSTER}
        alt=""
        aria-hidden
        className="absolute inset-0 h-full w-full object-cover"
        style={{ filter: MEDIA_FILTER }}
      />

      {mounted && !prefersReducedMotion && <MotionLoop slides={isMobile ? MOBILE_SLIDES : SLIDES} />}

      {/* Heavy wash -- the montage now reads as a slow, subtle backdrop
          (~20% visible) confined to the hero, not a bright photo the
          headline competes with. The hero's own headline gets further
          contrast from a local gradient/panel behind the text itself
          (see page.tsx). */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "linear-gradient(115deg, rgba(10,10,11,0.86) 0%, rgba(10,10,11,0.8) 35%, rgba(10,10,11,0.68) 65%, rgba(10,10,11,0.82) 100%)",
        }}
      />
      <div className="absolute inset-0 bg-gradient-to-b from-bg/30 via-bg/45 to-bg/70" />
    </div>
  );
}
