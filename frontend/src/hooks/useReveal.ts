import { useEffect, useState } from "react";

/** One-time fade-up when an element scrolls into view. */
export function useReveal<T extends HTMLElement>(): [(el: T | null) => void, string] {
  const [el, setEl] = useState<T | null>(null);
  const [shown, setShown] = useState(false);
  useEffect(() => {
    if (!el || shown) return;
    const obs = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          setShown(true);
          obs.disconnect();
        }
      },
      { threshold: 0.08 }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [el, shown]);
  return [setEl, shown ? "reveal is-shown" : "reveal"];
}
