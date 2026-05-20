import { useCountUp } from "../utils/useCountUp";

type Props = {
  currentSaudi: number;
  currentTotal: number;
  optimizedSaudi: number;
  optimizedTotal: number;
};

/**
 * Horizontal Saudization journey band — sits between the KPI strip and the
 * donut breakdown. Single-row layout so the whole Results summary fits on a
 * laptop screen.
 *
 *   ┌────────────────────────────────────────────────────────────────────┐
 *   │ SAUDIZATION JOURNEY                          ▲ +8.7 pp · +22 Saudis│
 *   │ 23.4% ─────────────────► 32.1%                                    │
 *   │ ██████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
 *   │ ▲ Current 23.4%       ▲ Optimized 32.1%                            │
 *   │ From 361 to 383 in-house Saudis · excludes outsourced · pp = ...   │
 *   └────────────────────────────────────────────────────────────────────┘
 */
export function SaudizationHero({
  currentSaudi,
  currentTotal,
  optimizedSaudi,
  optimizedTotal,
}: Props) {
  const safeOptimizedTotal = Math.max(optimizedTotal, 1);
  const safeCurrentTotal = Math.max(currentTotal, 1);
  const optimizedRate = Math.max(0, Math.min(1, optimizedSaudi / safeOptimizedTotal));
  const currentRate = Math.max(0, Math.min(1, currentSaudi / safeCurrentTotal));
  const deltaPp = (optimizedRate - currentRate) * 100;
  const animatedOptimized = useCountUp(optimizedRate * 100, 700);
  const animatedCurrent = useCountUp(currentRate * 100, 600);

  const tone =
    Math.abs(deltaPp) < 0.05 ? "flat" : deltaPp > 0 ? "up" : "down";
  const deltaGlyph = tone === "up" ? "▲" : tone === "down" ? "▼" : "●";
  const deltaSign = deltaPp > 0 ? "+" : "";
  const newSaudiPositions = Math.round(optimizedSaudi - currentSaudi);
  const positionsChange =
    newSaudiPositions > 0
      ? `+${newSaudiPositions} Saudis`
      : newSaudiPositions < 0
        ? `${newSaudiPositions} Saudis`
        : "no change in Saudi headcount";

  // Bar positions (0–100). Used both for fill widths and for marker placement.
  const currentPct = currentRate * 100;
  const optimizedPct = optimizedRate * 100;

  return (
    <div className="saudization-hero">
      <span className="saudization-hero-motif" aria-hidden />

      <div className="saudization-hero-head">
        <span className="saudization-hero-eyebrow">Saudization Journey</span>
        <span
          className={`saudization-hero-delta saudization-hero-delta--${tone}`}
          title={`pp = percentage points (absolute difference between rates). Current ${currentPct.toFixed(1)}%, optimized ${optimizedPct.toFixed(1)}%.`}
          aria-label={`${deltaSign}${deltaPp.toFixed(1)} percentage points, ${positionsChange}`}
        >
          <span aria-hidden>{deltaGlyph}</span>
          {`${deltaSign}${deltaPp.toFixed(1)} pp`}
          <span className="saudization-hero-delta-sep" aria-hidden>·</span>
          <span className="saudization-hero-delta-positions">{positionsChange}</span>
        </span>
      </div>

      <div className="saudization-hero-rates">
        <span className="saudization-hero-rate saudization-hero-rate--current">
          <span className="saudization-hero-rate-tag">Current</span>
          <span className="saudization-hero-rate-value">{animatedCurrent.toFixed(1)}%</span>
        </span>
        <span className="saudization-hero-arrow" aria-hidden>──────►</span>
        <span className="saudization-hero-rate saudization-hero-rate--optimized">
          <span className="saudization-hero-rate-tag">Optimized</span>
          <span className="saudization-hero-rate-value">{animatedOptimized.toFixed(1)}%</span>
        </span>
      </div>

      <div
        className="saudization-hero-bar"
        role="img"
        aria-label={`Saudization moves from ${currentPct.toFixed(1)}% to ${optimizedPct.toFixed(1)}%`}
      >
        {/* Ghost-fill: 0 → current. Sits behind the optimized fill. */}
        <span
          className="saudization-hero-bar-fill saudization-hero-bar-fill--current"
          style={{ width: `${currentPct}%` }}
          aria-hidden
        />
        {/* Optimized fill: 0 → optimized. Brighter green with flag-stripe at the leading edge. */}
        <span
          className="saudization-hero-bar-fill saudization-hero-bar-fill--optimized"
          style={{ width: `${optimizedPct}%` }}
          aria-hidden
        />
        {/* Markers — small wedges that pin Current and Optimized on the 0–100 axis. */}
        <span
          className="saudization-hero-bar-marker saudization-hero-bar-marker--current"
          style={{ left: `${currentPct}%` }}
          aria-hidden
          title={`Current ${currentPct.toFixed(1)}%`}
        />
        <span
          className="saudization-hero-bar-marker saudization-hero-bar-marker--optimized"
          style={{ left: `${optimizedPct}%` }}
          aria-hidden
          title={`Optimized ${optimizedPct.toFixed(1)}%`}
        />
      </div>

      <p className="saudization-hero-sub">
        From <strong>{Math.round(currentSaudi).toLocaleString()}</strong>
        {" "}to <strong>{Math.round(optimizedSaudi).toLocaleString()}</strong> in-house Saudis
        {" "}<span className="saudization-hero-sep">·</span>{" "}
        Excludes outsourced workers (Nitaqat){" "}
        <span className="saudization-hero-sep">·</span>{" "}
        pp = percentage points
      </p>
    </div>
  );
}
