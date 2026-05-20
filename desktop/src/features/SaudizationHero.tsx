import { useCountUp } from "../utils/useCountUp";

const saudiFlagUrl = new URL("../assets/sa-flag.png", import.meta.url).href;

type Props = {
  currentSaudi: number;
  currentTotal: number;
  optimizedSaudi: number;
  optimizedTotal: number;
};

/**
 * Saudization showcase card — single-row design that uses the Saudi flag as
 * the visual focal point, with the optimized rate as the hero number, delta
 * pill inline, and a single supporting line.
 *
 *   ┌──────┐   SAUDIZATION
 *   │      │
 *   │ 🇸🇦  │   32.1%    ▲ +8.7 pp
 *   │      │   ─
 *   └──────┘   From 23.4% · 361 → 383 in-house Saudis (+22 positions)
 *
 * Sits between the KPI grid and the donut breakdown. Height ~92px.
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
      ? `+${newSaudiPositions} positions added`
      : newSaudiPositions < 0
        ? `${Math.abs(newSaudiPositions)} positions reduced`
        : "no change";

  return (
    <div className={`saudization-showcase saudization-showcase--${tone}`}>
      <div className="saudization-showcase-flag" aria-hidden>
        <img src={saudiFlagUrl} alt="" />
      </div>

      <div className="saudization-showcase-body">
        <span className="saudization-showcase-eyebrow">Saudization</span>
        <div className="saudization-showcase-row">
          <span className="saudization-showcase-value">{animatedOptimized.toFixed(1)}%</span>
          <span
            className={`saudization-showcase-delta saudization-showcase-delta--${tone}`}
            aria-label={`${deltaSign}${deltaPp.toFixed(1)} percentage points vs current`}
          >
            <span aria-hidden>{deltaGlyph}</span>
            {`${deltaSign}${deltaPp.toFixed(1)} pp`}
          </span>
          <span
            className="saudization-showcase-help"
            title="Rate = in-house Saudis ÷ in-house workforce (Nitaqat, excludes outsourced). pp = percentage points."
            aria-label="Saudization methodology"
          >
            ⓘ
          </span>
        </div>
        <p className="saudization-showcase-sub">
          From <strong>{(currentRate * 100).toFixed(1)}%</strong> ·
          {" "}<strong>{Math.round(currentSaudi).toLocaleString()}</strong>
          {" "}→{" "}<strong>{Math.round(optimizedSaudi).toLocaleString()}</strong>
          {" "}in-house Saudis ·
          {" "}{positionsLabel}
        </p>
      </div>
    </div>
  );
}
