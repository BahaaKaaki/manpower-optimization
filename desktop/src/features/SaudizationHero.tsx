import { useCountUp } from "../utils/useCountUp";

const saudiFlagUrl = new URL("../assets/sa-flag.png", import.meta.url).href;

type Props = {
  currentSaudi: number;
  currentTotal: number;
  optimizedSaudi: number;
  optimizedTotal: number;
};

/**
 * Single-line Saudization strip — non-intrusive footnote that lives between
 * the KPI grid and the donut breakdown. The donut chart already shows the
 * proportional Saudi vs Non-Saudi vs Outsourced split visually; this strip
 * just adds the rate-level narrative (current → optimized + Saudi headcount
 * change) in one elegant row of typography.
 *
 *   🇸🇦  SAUDIZATION   23.4% → 32.1%   ▲ +8.7 pp   361 → 383 Saudis (+22)  ⓘ
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

  const animatedOptimized = useCountUp(optimizedRate * 100, 600);

  const tone =
    Math.abs(deltaPp) < 0.05 ? "flat" : deltaPp > 0 ? "up" : "down";
  const deltaGlyph = tone === "up" ? "▲" : tone === "down" ? "▼" : "●";
  const deltaSign = deltaPp > 0 ? "+" : "";
  const newSaudiPositions = Math.round(optimizedSaudi - currentSaudi);
  const positionsLabel =
    newSaudiPositions > 0
      ? `+${newSaudiPositions}`
      : newSaudiPositions < 0
        ? `${newSaudiPositions}`
        : "±0";

  return (
    <div className={`saudization-strip saudization-strip--${tone}`}>
      <img
        src={saudiFlagUrl}
        width="20"
        height="14"
        alt=""
        aria-hidden
        className="saudization-strip-flag"
      />
      <span className="saudization-strip-label">Saudization</span>

      <span className="saudization-strip-rates">
        <span className="saudization-strip-current">{(currentRate * 100).toFixed(1)}%</span>
        <span className="saudization-strip-arrow" aria-hidden>→</span>
        <span className="saudization-strip-optimized">{animatedOptimized.toFixed(1)}%</span>
      </span>

      <span
        className={`saudization-strip-delta saudization-strip-delta--${tone}`}
        aria-label={`${deltaSign}${deltaPp.toFixed(1)} percentage points`}
      >
        <span aria-hidden>{deltaGlyph}</span>
        {`${deltaSign}${deltaPp.toFixed(1)} pp`}
      </span>

      <span className="saudization-strip-positions">
        {Math.round(currentSaudi).toLocaleString()} → {Math.round(optimizedSaudi).toLocaleString()} Saudis ({positionsLabel})
      </span>

      <span
        className="saudization-strip-help"
        title={`Rate = in-house Saudis ÷ in-house workforce (Nitaqat — outsourced workers are excluded). pp = percentage points, the absolute difference between two rates.`}
        aria-label="Saudization methodology"
      >
        ⓘ
      </span>
    </div>
  );
}
