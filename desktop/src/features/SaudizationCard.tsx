import { useCountUp } from "../utils/useCountUp";

type Props = {
  variant: "current" | "optimized";
  saudiCount: number;
  totalCount: number;
  /** Optimized-only: percentage-point delta vs the Current rate. */
  deltaPp?: number | null;
};

export function SaudizationCard({ variant, saudiCount, totalCount, deltaPp }: Props) {
  const safeDenom = Math.max(totalCount, 1);
  const fraction = saudiCount / safeDenom;
  const pct = Math.max(0, Math.min(1, fraction)) * 100;
  const animated = useCountUp(pct, 500);

  const tone =
    deltaPp == null
      ? null
      : Math.abs(deltaPp) < 0.05
        ? "flat"
        : deltaPp > 0
          ? "up"
          : "down";
  const deltaGlyph = tone === "up" ? "▲" : tone === "down" ? "▼" : "●";
  const deltaSign = deltaPp != null && deltaPp > 0 ? "+" : "";

  return (
    <div className="saudization-card">
      <span className="saudization-card-eyebrow">
        Saudization · {variant === "current" ? "Current" : "Optimized"}
      </span>
      <div className="saudization-card-row">
        <span className="saudization-card-value">{animated.toFixed(1)}%</span>
        {variant === "optimized" && deltaPp != null ? (
          <span
            className={`saudization-card-delta${tone && tone !== "up" ? ` saudization-card-delta--${tone}` : ""}`}
            aria-label={`${deltaSign}${deltaPp.toFixed(1)} percentage points vs current`}
          >
            <span aria-hidden>{deltaGlyph}</span>
            {`${deltaSign}${deltaPp.toFixed(1)} pp vs current`}
          </span>
        ) : null}
      </div>
      <div
        className="saudization-flag-bar"
        role="img"
        aria-label={`${pct.toFixed(1)} percent Saudization`}
      >
        <span
          className="saudization-flag-bar-fill"
          style={{ width: `${pct}%` }}
          aria-hidden
        />
      </div>
      <span className="saudization-card-sub">
        {Math.round(saudiCount).toLocaleString()} of {Math.round(totalCount).toLocaleString()} employees are Saudi
      </span>
    </div>
  );
}
