import { useCountUp } from "../utils/useCountUp";

const saudiFlagUrl = new URL("../assets/sa-flag.png", import.meta.url).href;

type Props = {
  currentSaudi: number;
  currentTotal: number;
  optimizedSaudi: number;
  optimizedTotal: number;
};

/**
 * Saudization showcase card.
 *
 *   ┌──────┐   SAUDIZATION                                              ⓘ
 *   │      │
 *   │ 🇸🇦  │   32.1%    ▲ +8.7 pp
 *   │      │   ─────────────────────────────────────────────
 *   └──────┘   CURRENT │ IN-HOUSE SAUDIS │ NEW POSITIONS
 *              23.4%   │ 361 → 383       │ +22 added
 *
 * Flag is the visual focal point (left); big optimized rate is the hero
 * number; supporting stats live in a labeled mini-grid below for at-a-glance
 * scannability (vs the previous dot-separated wall of text).
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
  const animatedOptimized = useCountUp(optimizedRate * 100, 720);

  const tone =
    Math.abs(deltaPp) < 0.05 ? "flat" : deltaPp > 0 ? "up" : "down";
  const deltaGlyph = tone === "up" ? "▲" : tone === "down" ? "▼" : "●";
  const deltaSign = deltaPp > 0 ? "+" : "";
  const newSaudiPositions = Math.round(optimizedSaudi - currentSaudi);
  const positionsLabel =
    newSaudiPositions > 0
      ? `+${newSaudiPositions} added`
      : newSaudiPositions < 0
        ? `${Math.abs(newSaudiPositions)} reduced`
        : "no change";

  return (
    <div className={`saudization-showcase saudization-showcase--${tone}`}>
      <div className="saudization-showcase-flag" aria-hidden>
        <img src={saudiFlagUrl} alt="" />
      </div>

      <div className="saudization-showcase-body">
        <div className="saudization-showcase-head">
          <span className="saudization-showcase-eyebrow">Saudization</span>
          <span
            className="saudization-showcase-help"
            title="Rate = in-house Saudis ÷ in-house workforce (Nitaqat, excludes outsourced). pp = percentage points, the absolute difference between two rates."
            aria-label="Saudization methodology"
          >
            ⓘ
          </span>
        </div>

        <div className="saudization-showcase-headline">
          <span className="saudization-showcase-value">{animatedOptimized.toFixed(1)}%</span>
          <span
            className={`saudization-showcase-delta saudization-showcase-delta--${tone}`}
            aria-label={`${deltaSign}${deltaPp.toFixed(1)} percentage points vs current`}
          >
            <span aria-hidden>{deltaGlyph}</span>
            {`${deltaSign}${deltaPp.toFixed(1)} pp`}
          </span>
        </div>

        <div className="saudization-showcase-stats" role="list">
          <div className="saudization-showcase-stat" role="listitem">
            <span className="saudization-showcase-stat-label">Current rate</span>
            <span className="saudization-showcase-stat-value">{(currentRate * 100).toFixed(1)}%</span>
          </div>
          <div className="saudization-showcase-stat" role="listitem">
            <span className="saudization-showcase-stat-label">In-house Saudis</span>
            <span className="saudization-showcase-stat-value">
              {Math.round(currentSaudi).toLocaleString()}
              <span className="saudization-showcase-stat-arrow" aria-hidden> → </span>
              {Math.round(optimizedSaudi).toLocaleString()}
            </span>
          </div>
          <div className="saudization-showcase-stat" role="listitem">
            <span className="saudization-showcase-stat-label">New positions</span>
            <span className="saudization-showcase-stat-value">{positionsLabel}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
