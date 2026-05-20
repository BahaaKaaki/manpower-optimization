import { useCountUp } from "../utils/useCountUp";

type Props = {
  currentSaudi: number;
  currentTotal: number;
  optimizedSaudi: number;
  optimizedTotal: number;
};

const RADIUS_OUTER = 64;
const RADIUS_INNER = 50;
const STROKE_OUTER = 12;
const STROKE_INNER = 5;
const SIZE = 160;
const CENTER = SIZE / 2;
const CIRC_OUTER = 2 * Math.PI * RADIUS_OUTER;
const CIRC_INNER = 2 * Math.PI * RADIUS_INNER;

/**
 * Hero Saudization card — promoted to its own row above the donut breakdown.
 *
 * Layout:
 *  ┌───────────────────────────────────────────────────────────────────┐
 *  │  ┌────────┐    SAUDIZATION JOURNEY                                │
 *  │  │  ring  │    32.1% Saudis after optimization                    │
 *  │  │ gauge  │    [+8.7 pp ▲]                                        │
 *  │  └────────┘    From 89 to 124 Saudi employees · +35 positions     │
 *  └───────────────────────────────────────────────────────────────────┘
 *
 * The ring shows the OPTIMIZED rate as the bold outer arc; an inner thin
 * arc shows the CURRENT rate so the eye sees the delta at a glance.
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

  const animatedPct = useCountUp(optimizedRate * 100, 700);

  const tone =
    Math.abs(deltaPp) < 0.05 ? "flat" : deltaPp > 0 ? "up" : "down";
  const deltaGlyph = tone === "up" ? "▲" : tone === "down" ? "▼" : "●";
  const deltaSign = deltaPp > 0 ? "+" : "";

  const newSaudiPositions = Math.round(optimizedSaudi - currentSaudi);

  // Compute strokeDashoffset for both arcs. Both arcs start at the top (rotated -90°).
  const outerDashOffset = CIRC_OUTER * (1 - optimizedRate);
  const innerDashOffset = CIRC_INNER * (1 - currentRate);

  return (
    <div className="saudization-hero">
      {/* Decorative flag-stripe motif in the top-right corner */}
      <span className="saudization-hero-motif" aria-hidden />

      <div className="saudization-hero-ring-wrap">
        <svg
          viewBox={`0 0 ${SIZE} ${SIZE}`}
          width={SIZE}
          height={SIZE}
          className="saudization-hero-ring"
          role="img"
          aria-label={`Optimized Saudization ${optimizedRate * 100}%, current ${currentRate * 100}%`}
        >
          {/* Outer track (unfilled remainder) */}
          <circle
            cx={CENTER}
            cy={CENTER}
            r={RADIUS_OUTER}
            fill="none"
            stroke="rgba(255, 255, 255, 0.12)"
            strokeWidth={STROKE_OUTER}
          />
          {/* Outer arc — OPTIMIZED rate */}
          <circle
            cx={CENTER}
            cy={CENTER}
            r={RADIUS_OUTER}
            fill="none"
            stroke="url(#saudiHeroGradient)"
            strokeWidth={STROKE_OUTER}
            strokeLinecap="round"
            strokeDasharray={CIRC_OUTER}
            strokeDashoffset={outerDashOffset}
            transform={`rotate(-90 ${CENTER} ${CENTER})`}
            className="saudization-hero-ring-outer"
          />
          {/* Inner track */}
          <circle
            cx={CENTER}
            cy={CENTER}
            r={RADIUS_INNER}
            fill="none"
            stroke="rgba(255, 255, 255, 0.06)"
            strokeWidth={STROKE_INNER}
          />
          {/* Inner arc — CURRENT rate (dashed line evokes "the past") */}
          <circle
            cx={CENTER}
            cy={CENTER}
            r={RADIUS_INNER}
            fill="none"
            stroke="rgba(255, 255, 255, 0.65)"
            strokeWidth={STROKE_INNER}
            strokeLinecap="round"
            strokeDasharray="3 6"
            transform={`rotate(-90 ${CENTER} ${CENTER})`}
            style={{
              strokeDasharray: `${CIRC_INNER * currentRate} ${CIRC_INNER}`,
              strokeDashoffset: innerDashOffset,
            }}
            className="saudization-hero-ring-inner"
          />
          <defs>
            <linearGradient id="saudiHeroGradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#7fcc5e" />
              <stop offset="100%" stopColor="#3e7d24" />
            </linearGradient>
          </defs>
          <text
            x={CENTER}
            y={CENTER + 4}
            textAnchor="middle"
            className="saudization-hero-ring-value"
          >
            {animatedPct.toFixed(1)}%
          </text>
          <text
            x={CENTER}
            y={CENTER + 22}
            textAnchor="middle"
            className="saudization-hero-ring-caption"
          >
            {`current ${(currentRate * 100).toFixed(1)}%`}
          </text>
        </svg>
      </div>

      <div className="saudization-hero-body">
        <span className="saudization-hero-eyebrow">Saudization Journey</span>
        <h3 className="saudization-hero-headline">
          {(optimizedRate * 100).toFixed(1)}% Saudis after optimization
        </h3>
        <span
          className={`saudization-hero-delta saudization-hero-delta--${tone}`}
          aria-label={`${deltaSign}${deltaPp.toFixed(1)} percentage points vs current`}
        >
          <span aria-hidden>{deltaGlyph}</span>
          {`${deltaSign}${deltaPp.toFixed(1)} pp vs current`}
        </span>
        <p className="saudization-hero-sub">
          From <strong>{Math.round(currentSaudi).toLocaleString()}</strong>
          {" "}to <strong>{Math.round(optimizedSaudi).toLocaleString()}</strong> Saudi employees
          {newSaudiPositions > 0
            ? ` · +${newSaudiPositions} positions added`
            : newSaudiPositions < 0
              ? ` · ${Math.abs(newSaudiPositions)} positions reduced`
              : ""}
        </p>
      </div>
    </div>
  );
}
