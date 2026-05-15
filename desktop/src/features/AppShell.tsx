import type { AppStage, BusyAction } from "../types";

const logoUrl = "/cpc-logo.png";

const workflowSteps: { id: AppStage; label: string }[] = [
  { id: "home", label: "Home Page" },
  { id: "upload", label: "Data Upload" },
  { id: "mappings", label: "Additional Inputs" },
  { id: "ready", label: "User Assumptions" },
  { id: "results", label: "Output" },
];

function UploadIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden="true">
      <path d="M7.5 1.5V10M7.5 1.5L4.5 4.5M7.5 1.5L10.5 4.5M2 12.5H13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

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

const stageTitles: Record<AppStage, { eyebrow: string; title: string }> = {
  home: { eyebrow: "Home Page", title: "Manpower Optimization Tool" },
  upload: { eyebrow: "Data Upload", title: "Upload Workbook" },
  mappings: { eyebrow: "Additional Inputs", title: "Job Families" },
  ready: { eyebrow: "User Assumptions", title: "Optimization Mode" },
  results: { eyebrow: "Output", title: "Output Summary" },
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
  busyAction: BusyAction;
  canRun: boolean;
  canResumeResults: boolean;
  onUploadClick: () => void;
  onRunOptimization: () => void;
  onResumeResults: () => void;
  onDownload?: () => void;
  onNavigate?: (stage: AppStage) => void;
  children: React.ReactNode;
};

export function AppShell({
  stage,
  reachableStages,
  stageBadges,
  apiReady,
  status,
  busyAction,
  canRun,
  canResumeResults,
  onUploadClick,
  onRunOptimization,
  onResumeResults,
  onDownload,
  onNavigate,
  children,
}: AppShellProps) {
  const { eyebrow, title } = stageTitles[stage];

  if (stage === "home") {
    return <div className="layout-root layout-root--home">{children}</div>;
  }

  return (
    <div className="layout-root">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <img src={logoUrl} alt="Workforce Studio" className="sidebar-logo" />
          <div className="sidebar-brand-text">
            <span className="sidebar-brand-label">Workforce Studio</span>
            <span className="sidebar-brand-name">Manpower Optimizer</span>
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
          <div className="engine-status">
            <span className={`engine-dot ${apiReady ? "ready" : ""}`} />
            <div className="engine-status-text">
              <span className="engine-status-label">Engine status</span>
              <span className="engine-status-value">{status}</span>
            </div>
          </div>
          <button
            className="sidebar-action upload"
            disabled={!apiReady || busyAction === "upload"}
            onClick={onUploadClick}
          >
            <UploadIcon />
            <span>{canRun ? "Upload new workbook" : "Upload workbook"}</span>
          </button>
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
            <span className="topbar-eyebrow">{eyebrow}</span>
            <h1 className="topbar-title">{title}</h1>
          </div>
          <div className="topbar-actions">
            {stage === "results" && onDownload && (
              <button className="btn btn-primary btn-sm" onClick={onDownload}>
                <DownloadIcon /> Download Excel
              </button>
            )}
          </div>
        </div>
        <div className="content-body">
          <div className="content-body-inner" key={stage}>
            {children}
          </div>
        </div>
      </main>
    </div>
  );
}

export { DownloadIcon };
