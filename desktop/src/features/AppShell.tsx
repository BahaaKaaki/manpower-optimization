import type { AppStage } from "../types";

const logoUrl = "/cpc-logo.png";

const workflowSteps: { id: AppStage; label: string }[] = [
  { id: "home", label: "Home Page" },
  { id: "bu-selection", label: "BU Selection" },
  { id: "upload", label: "Data Upload" },
  { id: "mode", label: "Optimization Mode" },
  { id: "ready", label: "User Assumptions" },
  { id: "results", label: "Output" },
];

function PlayIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <path d="M3 2L12 7L3 12V2Z" fill="currentColor"/>
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
      <path d="M2 6L5 9L10 3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden="true">
      <path d="M7.5 1.5V10M7.5 10L4.5 7M7.5 10L10.5 7M2 12.5H13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

function ExcelExportIcon() {
  // Spreadsheet-grid mark with a small download arrow on top — reads as "Excel
  // export" without being a literal Excel logo (avoids trademark territory).
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect x="2.5" y="3.5" width="11" height="9" rx="1.4" stroke="currentColor" strokeWidth="1.3" />
      <path d="M2.5 7.5h11M2.5 10.5h11M6 3.5v9M10 3.5v9" stroke="currentColor" strokeWidth="1.1" opacity="0.7" />
      <path d="M8 5.2v2.4M8 7.6l-1.2-1M8 7.6l1.2-1" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ChevronLeftIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <path d="M9 2L4 7L9 12" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

function ChevronRightIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <path d="M5 2L10 7L5 12" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

const STAGE_ORDER: AppStage[] = [
  "home",
  "bu-selection",
  "upload",
  "mode",
  "ready",
  "results",
];
const STAGE_LABELS: Record<AppStage, string> = {
  home: "Home Page",
  "bu-selection": "BU Selection",
  upload: "Data Upload",
  mode: "Optimization Mode",
  ready: "User Assumptions",
  results: "Output",
};

const stageTitles: Record<AppStage, { eyebrow: string }> = {
  home: { eyebrow: "Home Page" },
  "bu-selection": { eyebrow: "BU Selection" },
  upload: { eyebrow: "Data Upload" },
  mode: { eyebrow: "Optimization Mode" },
  ready: { eyebrow: "User Assumptions" },
  results: { eyebrow: "Output" },
};

export type StageBadgeTone = "neutral" | "positive" | "warning" | "danger" | "info";

export type StageBadge = {
  label: string;
  tone?: StageBadgeTone;
};

type AppShellProps = {
  stage: AppStage;
  reachableStages: Set<AppStage>;
  stageBadges?: Partial<Record<AppStage, StageBadge | undefined>>;
  apiReady: boolean;
  status: string;
  canRun: boolean;
  canResumeResults: boolean;
  onResumeResults: () => void;
  onDownload?: () => void;
  onOpenGuide?: () => void;
  onNavigate?: (stage: AppStage) => void;
  children: React.ReactNode;
};

function GuideIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.4" />
      <path
        d="M6.2 6c.2-1 1-1.7 2-1.7 1.1 0 2 .8 2 1.9 0 .8-.5 1.3-1.3 1.6-.5.2-.9.5-.9 1.1V9.2M8 11.4h.01"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function AppShell({
  stage,
  reachableStages,
  stageBadges,
  apiReady,
  status,
  canRun,
  canResumeResults,
  onResumeResults,
  onDownload,
  onOpenGuide,
  onNavigate,
  children,
}: AppShellProps) {
  const { eyebrow } = stageTitles[stage];

  if (stage === "home") {
    return <div className="layout-root layout-root--home">{children}</div>;
  }

  return (
    <div className="layout-root">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="sidebar-brand-text">
            <span className="sidebar-brand-name">Manpower</span>
            <span className="sidebar-brand-sub">Optimization Tool</span>
          </div>
        </div>

        <nav className="sidebar-nav" aria-label="Workflow progress">
          {workflowSteps.map((step, index) => {
            const isActive = step.id === stage;
            const isReachable = reachableStages.has(step.id);
            // "completed" is the styling for any non-active step the user can navigate to.
            // "future" is for steps whose data does not yet exist.
            const state = isActive
              ? "active"
              : isReachable
              ? "completed"
              : "future";
            const clickable = !isActive && isReachable && !!onNavigate;
            const badge = stageBadges?.[step.id];
            return (
              <div key={step.id}>
                {index > 0 && <div className="nav-step-connector" />}
                <div
                  className={`nav-step ${state}${clickable ? " clickable" : ""}`}
                  onClick={clickable ? () => onNavigate(step.id) : undefined}
                  role={clickable ? "button" : undefined}
                  tabIndex={clickable ? 0 : undefined}
                  onKeyDown={clickable ? (e) => { if (e.key === "Enter" || e.key === " ") onNavigate(step.id); } : undefined}
                  aria-current={isActive ? "step" : undefined}
                >
                  <div className="nav-step-rail" aria-hidden />
                  <div className="nav-step-badge">
                    {state === "completed" ? <CheckIcon /> : index + 1}
                  </div>
                  <div className="nav-step-text">
                    <span className="nav-step-label">{step.label}</span>
                    {badge ? (
                      <span className={`nav-step-state nav-step-state--${badge.tone ?? "neutral"}`}>
                        {badge.label}
                      </span>
                    ) : null}
                  </div>
                </div>
              </div>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <img src={logoUrl} alt="CPC" className="sidebar-footer-logo" />
          <div className="engine-status">
            <span className={`engine-dot ${apiReady ? "ready" : ""}`} />
            <div className="engine-status-text">
              <span className="engine-status-label">Engine status</span>
              <span className="engine-status-value">{status}</span>
            </div>
          </div>
          {!canRun && canResumeResults && (
            <button className="sidebar-action upload" onClick={onResumeResults}>
              <span>Resume last results</span>
            </button>
          )}
        </div>
      </aside>

      <main className="content-root">
        <div className="content-topbar">
          <div className="topbar-title-group">
            <h1 className="topbar-eyebrow">{eyebrow}</h1>
          </div>
          <div className="topbar-actions">
            {stage === "results" && onDownload && (
              <button
                type="button"
                className="topbar-export-btn"
                onClick={onDownload}
                aria-label="Export optimization results as Excel"
              >
                <ExcelExportIcon />
                <span className="topbar-export-btn-text">
                  <span className="topbar-export-btn-title">Export Results</span>
                  <span className="topbar-export-btn-sub">XLSX · ready to download</span>
                </span>
              </button>
            )}
            {onOpenGuide && (
              <button
                type="button"
                className="topbar-guide-btn"
                onClick={onOpenGuide}
                aria-label="Open user guide"
                title="How to use this tool"
              >
                <GuideIcon />
                <span>Guide</span>
              </button>
            )}
          </div>
        </div>
        <div className="content-body">
          <div className="content-body-inner" key={stage}>
            {children}
            <StageNav
              stage={stage}
              reachableStages={reachableStages}
              onNavigate={onNavigate}
            />
          </div>
        </div>
      </main>
    </div>
  );
}

function StageNav({
  stage,
  reachableStages,
  onNavigate,
}: {
  stage: AppStage;
  reachableStages: Set<AppStage>;
  onNavigate?: (stage: AppStage) => void;
}) {
  const currentIndex = STAGE_ORDER.indexOf(stage);
  const prevStage = currentIndex > 0 ? STAGE_ORDER[currentIndex - 1] : null;
  const nextStage = currentIndex < STAGE_ORDER.length - 1 ? STAGE_ORDER[currentIndex + 1] : null;
  const canGoPrev = !!prevStage && !!onNavigate && reachableStages.has(prevStage);
  const canGoNext = !!nextStage && !!onNavigate && reachableStages.has(nextStage);

  if (!canGoPrev && !canGoNext) return null;

  return (
    <nav className="stage-nav" aria-label="Workflow navigation">
      <button
        type="button"
        className="stage-nav-btn stage-nav-btn--prev"
        disabled={!canGoPrev}
        onClick={canGoPrev && onNavigate ? () => onNavigate(prevStage!) : undefined}
        aria-label={prevStage ? `Go back to ${STAGE_LABELS[prevStage]}` : "No previous step"}
      >
        <ChevronLeftIcon />
        <span className="stage-nav-text">
          <span className="stage-nav-eyebrow">Previous</span>
          <span className="stage-nav-label">{prevStage ? STAGE_LABELS[prevStage] : "None"}</span>
        </span>
      </button>
      <button
        type="button"
        className="stage-nav-btn stage-nav-btn--next"
        disabled={!canGoNext}
        onClick={canGoNext && onNavigate ? () => onNavigate(nextStage!) : undefined}
        aria-label={nextStage ? `Go forward to ${STAGE_LABELS[nextStage]}` : "No next step"}
      >
        <span className="stage-nav-text">
          <span className="stage-nav-eyebrow">Next</span>
          <span className="stage-nav-label">{nextStage ? STAGE_LABELS[nextStage] : "None"}</span>
        </span>
        <ChevronRightIcon />
      </button>
    </nav>
  );
}

export { DownloadIcon };
