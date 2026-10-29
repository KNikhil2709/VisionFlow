import { useEffect, useRef, useState } from "react";

/** Poll an async fn on an interval. Simpler and more robust than SSE for a
 * local demo, and keeps the UI live as runs move through the pipeline. */
export function usePolling<T>(fn: () => Promise<T>, intervalMs = 700): T | null {
  const [data, setData] = useState<T | null>(null);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const d = await fnRef.current();
        if (alive) setData(d);
      } catch {
        /* backend not up yet; keep last value */
      }
    };
    tick();
    const t = setInterval(tick, intervalMs);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [intervalMs]);
  return data;
}
