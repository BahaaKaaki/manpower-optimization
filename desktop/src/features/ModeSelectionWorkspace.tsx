import type { Settings } from "../types";

type Props = {
  settings: Settings;
  onUpdate: <K extends keyof Settings>(key: K, value: Settings[K]) => void;
};

export function ModeSelectionWorkspace({ settings, onUpdate }: Props) {
  const isTargetMode = settings.optimization_mode === "target";

  function pick(mode: Settings["optimization_mode"]) {
    onUpdate("optimization_mode", mode);
  }

  return (
    <section className="mode-step">
      <p className="mode-step-hint">
        Pick how the tool should optimize your workforce. You can change this any time on
        this step. In <strong>Target Manpower Plan</strong> mode the next step lets you add
        new job families that don't exist in your uploaded payroll.
      </p>

      <div className="mode-card-grid" role="radiogroup" aria-label="Optimization mode">
        <button
          type="button"
          className={`mode-card${!isTargetMode ? " mode-card--active" : ""}`}
          role="radio"
          aria-checked={!isTargetMode}
          onClick={() => pick("current")}
        >
          <span className="mode-card-icon" aria-hidden>
            <svg viewBox="0 0 24 24" fill="none">
              <path
                d="M3 20V11.5L12 4l9 7.5V20H14v-6h-4v6H3Z"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </span>
          <span className="mode-card-text">
            <span className="mode-card-title">Optimize Current Manpower</span>
            <span className="mode-card-desc">
              Keep today's total headcount. The tool finds the cheapest in house and outsourced mix.
            </span>
          </span>
          <span className="mode-card-check" aria-hidden>
            <svg viewBox="0 0 16 16" fill="none">
              <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5" />
              <path
                d="M5 8.4L7.1 10.5L11 6.5"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </span>
        </button>

        <button
          type="button"
          className={`mode-card${isTargetMode ? " mode-card--active" : ""}`}
          role="radio"
          aria-checked={isTargetMode}
          onClick={() => pick("target")}
        >
          <span className="mode-card-icon" aria-hidden>
            <svg viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="8.5" stroke="currentColor" strokeWidth="1.6" />
              <circle cx="12" cy="12" r="4.5" stroke="currentColor" strokeWidth="1.6" />
              <circle cx="12" cy="12" r="1.4" fill="currentColor" />
            </svg>
          </span>
          <span className="mode-card-text">
            <span className="mode-card-title">Input and Optimize a Target Manpower Plan</span>
            <span className="mode-card-desc">
              Type the headcount you want per family. The tool plans the cheapest way to get there.
            </span>
          </span>
          <span className="mode-card-check" aria-hidden>
            <svg viewBox="0 0 16 16" fill="none">
              <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5" />
              <path
                d="M5 8.4L7.1 10.5L11 6.5"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </span>
        </button>
      </div>

    </section>
  );
}
