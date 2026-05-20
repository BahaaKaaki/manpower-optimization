import { useEffect, useRef, useState } from "react";

/**
 * Animate a numeric value from 0 → target over `durationMs`. Respects
 * `prefers-reduced-motion`: returns the target value immediately when the user
 * has motion reduced. Re-runs whenever `target` changes (typical use: hook is
 * called inside a component, the target comes from props or state).
 */
export function useCountUp(target: number, durationMs = 500): number {
  const [value, setValue] = useState(target);
  const startRef = useRef<number | null>(null);
  const frameRef = useRef<number | null>(null);

  useEffect(() => {
    if (
      typeof window === "undefined" ||
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
    ) {
      setValue(target);
      return;
    }

    const from = 0;
    const span = target - from;
    startRef.current = null;

    function tick(timestamp: number) {
      if (startRef.current === null) startRef.current = timestamp;
      const elapsed = timestamp - startRef.current;
      const progress = Math.min(1, elapsed / durationMs);
      // Ease-out cubic for a snappy settle.
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(from + span * eased);
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(tick);
      }
    }

    frameRef.current = requestAnimationFrame(tick);
    return () => {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
    };
  }, [target, durationMs]);

  return value;
}
