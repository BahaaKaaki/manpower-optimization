import { useEffect } from "react";

type Props = {
  open: boolean;
  onClose: () => void;
};

/**
 * User Guide — right-side slide-in drawer. Concise, client-facing reference
 * for what the tool does + how to use it + key terminology. Opened from the
 * top-bar Guide button; closes on Escape or backdrop click.
 *
 * Designed to be a quick lookup, not a manual — 3 sections kept short.
 */
export function UserGuide({ open, onClose }: Props) {
  // ESC closes
  useEffect(() => {
    if (!open) return;
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  // Lock body scroll while open
  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open]);

  return (
    <>
      <div
        className={`user-guide-backdrop${open ? " user-guide-backdrop--open" : ""}`}
        onClick={onClose}
        aria-hidden={!open}
      />
      <aside
        className={`user-guide${open ? " user-guide--open" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="user-guide-title"
        aria-hidden={!open}
      >
        <header className="user-guide-head">
          <div className="user-guide-head-text">
            <span className="user-guide-eyebrow">Quick Reference</span>
            <h2 id="user-guide-title">How to use this tool</h2>
          </div>
          <button
            type="button"
            className="user-guide-close"
            onClick={onClose}
            aria-label="Close user guide"
          >
            <svg viewBox="0 0 16 16" fill="none" aria-hidden>
              <path d="M4 4l8 8m0-8l-8 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
          </button>
        </header>

        <div className="user-guide-body">
          <section className="user-guide-section">
            <h3>Overview</h3>
            <p>
              The Manpower Optimization Tool helps each <strong>CPC Holding Business Unit</strong> minimize
              payroll cost while meeting <strong>Saudization compliance</strong> (Nitaqat) and headcount
              targets. The optimizer rebalances in-house Saudi, in-house non-Saudi, and outsourced
              workers per job family using the BU's own configuration and your assumptions.
            </p>
          </section>

          <section className="user-guide-section">
            <h3>Workflow</h3>
            <ol className="user-guide-steps">
              <li>
                <strong>Choose a Business Unit.</strong> Each BU has its own profession / activity /
                job-family mappings. MGIC ships pre-configured; other BUs need their configuration
                Excel uploaded once.
              </li>
              <li>
                <strong>Configure (if needed).</strong> For a fresh BU, download the starter Excel,
                fill in your profession & activity mappings + job families + ratios, and upload it
                back via the Configuration panel.
              </li>
              <li>
                <strong>Upload payroll.</strong> Drop a single Excel workbook containing both your
                in-house and outsourced employee data. The tool validates structure and surfaces
                any unmapped roles before letting you proceed.
              </li>
              <li>
                <strong>Pick an optimization mode.</strong> "<em>Optimize current manpower</em>"
                keeps today's total headcount and finds the cheapest mix. "<em>Target manpower
                plan</em>" lets you set the headcount per job family.
              </li>
              <li>
                <strong>Set your assumptions.</strong> Saudization rate (overall + per family),
                risk factor, negotiated rates, workforce protection. Sensible defaults are
                pre-set, only override what you need.
              </li>
              <li>
                <strong>Run, review, export.</strong> Click "Run Optimization." The Output page
                shows total savings, recommended Saudi / Non-Saudi / Outsourced split per family,
                and the new Saudization rate. Export the full result as Excel from the top bar.
              </li>
            </ol>
          </section>

          <section className="user-guide-section">
            <h3>Key terms</h3>
            <dl className="user-guide-glossary">
              <dt>Job family</dt>
              <dd>A standard role grouping like Engineer, Skilled Labor, or Quarries Foreman. The
                optimizer plans headcount at this level.</dd>

              <dt>Saudization rate</dt>
              <dd>Saudi employees as a percentage of the <strong>in-house</strong> workforce.
                Outsourced workers are excluded. This matches the Nitaqat formula.</dd>

              <dt>Outsourceability</dt>
              <dd>A per-family rule: <em>Fully Outsourceable</em>, <em>Partially Outsourceable</em>,
                or <em>Not Outsourceable</em>. Set in the BU's Job Families sheet.</dd>

              <dt>pp (percentage points)</dt>
              <dd>The absolute difference between two percentages. Saudization going from 30% to
                35% is "+5 pp", not "+5%".</dd>

              <dt>Custom configuration</dt>
              <dd>A BU has a <em>custom</em> configuration when you've uploaded its own mapping
                Excel. Otherwise the BU runs on the tool's defaults.</dd>
            </dl>
          </section>

          <section className="user-guide-section user-guide-section--quiet">
            <p className="user-guide-footnote">
              Stuck on a step? Each stage shows inline hints and validation. The bottom Prev / Next
              bar lets you move freely once a stage is complete.
            </p>
          </section>
        </div>
      </aside>
    </>
  );
}
