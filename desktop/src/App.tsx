import { ChangeEvent, DragEvent, useEffect, useMemo, useRef, useState } from "react";

import {
  calculateTargetSplit as calculateTargetSplitRequest,
  checkHealth,
  initApiBase,
  reprocessWithMappings as reprocessWithMappingsRequest,
  resultsExportUrl,
  restoreResults,
  runOptimization as runOptimizationRequest,
  uploadWorkbook as uploadWorkbookRequest,
} from "./api/client";
import { AppShell, type StageBadge } from "./features/AppShell";
import { AssumptionsPanel } from "./features/AssumptionsPanel";
import { HomePage } from "./features/HomePage";
import { MappingResolveWorkspace } from "./features/MappingResolveWorkspace";
import { ResultsDashboard } from "./features/ResultsDashboard";
import { ScenarioControls } from "./features/ScenarioControls";
import { UploadWorkspace } from "./features/UploadWorkspace";
import type {
  ActivityProfession,
  AppStage,
  BusyAction,
  CustomFamilySpec,
  DetailTab,
  OptimizationResponse,
  Settings,
  UnmappedPair,
  UploadResponse,
} from "./types";
import { persistGet, persistSet } from "./utils/persistence";

const defaultSettings: Settings = {
  enforce_saudization: true,
  saudization_rate: 0.3,
  can_reduce_current_saudi: false,
  risk_factor: 0.25,
  negotiated_rates: false,
  negotiated_insurance_cost: 0,
  negotiated_service_margin: 0,
  protect_tenured_inhouse: false,
  tenure_threshold_years: 5,
  engineer_saudization_rate: 0.25,
  sales_saudization_rate: 0.6,
  management_saudization_rate: 0.35,
  saudi_cost_premium: 1.1,
  outsource_cost_discount: null,
  max_ratio_overrides: {},
  optimization_mode: "current",
  target_headcounts: {},
  custom_families: [],
};

function isDebugEnabled(): boolean {
  if (typeof window === "undefined") return false;
  const params = new URLSearchParams(window.location.search);
  return params.get("debug") === "1" || window.localStorage.getItem("cpc-debug") === "1";
}

export default function App() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [apiReady, setApiReady] = useState(false);
  const [status, setStatus] = useState("Starting engine...");
  const [error, setError] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<BusyAction>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadInfo, setUploadInfo] = useState<UploadResponse | null>(null);
  const [targetRows, setTargetRows] = useState<Record<string, unknown>[]>([]);
  const [optimization, setOptimization] = useState<OptimizationResponse | null>(null);
  const [restoredOptimization, setRestoredOptimization] = useState<OptimizationResponse | null>(null);
  const [settings, setSettings] = useState<Settings>(defaultSettings);
  const [detailTab, setDetailTab] = useState<DetailTab>("insights");
  const [activeStage, setActiveStage] = useState<AppStage>("home");
  const [debugEnabled] = useState(isDebugEnabled);
  const [unmappedPairs, setUnmappedPairs] = useState<UnmappedPair[]>([]);
  const [workbookPairs, setWorkbookPairs] = useState<ActivityProfession[]>([]);

  // Hydrate persisted custom_families on boot. Until the persistence layer reports back,
  // settings.custom_families is empty (the default). After hydration, any prior session's
  // user-defined families come back automatically.
  useEffect(() => {
    let cancelled = false;
    void persistGet<CustomFamilySpec[]>("custom_families", []).then((stored) => {
      if (cancelled || stored.length === 0) return;
      setSettings((current) => ({ ...current, custom_families: stored }));
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // Persist custom_families on every change. Save is fire-and-forget; persistence is
  // best-effort, not on the critical path.
  useEffect(() => {
    void persistSet("custom_families", settings.custom_families);
  }, [settings.custom_families]);

  const allMappingsResolved = unmappedPairs.length === 0;

  const reachableStages = useMemo<Set<AppStage>>(() => {
    const reachable = new Set<AppStage>(["home", "upload"]);
    if (uploadInfo) reachable.add("mappings");
    // Downstream stages stay blocked until every unmapped (activity, profession) pair has
    // a resolution. The user must visit the Job Families step to unblock optimization.
    if (uploadInfo && allMappingsResolved) reachable.add("ready");
    if (allMappingsResolved && optimization) reachable.add("results");
    return reachable;
  }, [uploadInfo, optimization, allMappingsResolved]);

  // Stage to display = user's selection when its data is still present, otherwise the
  // highest reachable stage. Lets the user navigate freely between any stage that has
  // data without destroying later stages on backwards navigation.
  const stage: AppStage = useMemo(() => {
    if (reachableStages.has(activeStage)) return activeStage;
    if (allMappingsResolved && optimization) return "results";
    if (uploadInfo && allMappingsResolved) return "ready";
    if (uploadInfo) return "mappings";
    return "upload";
  }, [activeStage, reachableStages, optimization, uploadInfo, allMappingsResolved]);

  // Per-step badges: surface real state in the sidebar (filename / unmapped count /
  // current vs target mode / optimization status) so the user can read progress at a
  // glance without clicking each step.
  const stageBadges = useMemo<Partial<Record<AppStage, StageBadge>>>(() => {
    const badges: Partial<Record<AppStage, StageBadge>> = {};

    if (uploadError) {
      badges.upload = { label: "Validation failed", tone: "danger" };
    } else if (busyAction === "upload") {
      badges.upload = { label: "Uploading…", tone: "info" };
    } else if (uploadInfo) {
      const filename = uploadInfo.filename ?? "Workbook loaded";
      const compact = filename.length > 22 ? `${filename.slice(0, 20)}…` : filename;
      badges.upload = { label: compact, tone: "positive" };
    }

    if (uploadInfo) {
      const unresolved = unmappedPairs.length;
      const customCount = settings.custom_families.length;
      if (unresolved > 0) {
        badges.mappings = {
          label: `${unresolved} unmapped`,
          tone: "danger",
        };
      } else if (customCount > 0) {
        badges.mappings = {
          label: `${customCount} custom`,
          tone: "positive",
        };
      } else {
        badges.mappings = { label: `${uploadInfo.job_family_count} families`, tone: "positive" };
      }
    }

    if (uploadInfo) {
      if (allMappingsResolved) {
        badges.ready = {
          label: settings.optimization_mode === "target" ? "Target plan" : "Current",
          tone: settings.optimization_mode === "target" ? "info" : "neutral",
        };
      } else {
        badges.ready = { label: "Resolve mappings", tone: "warning" };
      }
    }

    if (busyAction === "optimize") {
      badges.results = { label: "Optimizing…", tone: "info" };
    } else if (optimization) {
      const status = optimization.summary?.optimization_status ?? "";
      const isOptimal = status === "Optimal";
      badges.results = {
        label: isOptimal ? "Optimal" : status || "Done",
        tone: isOptimal ? "positive" : "warning",
      };
    } else if (allMappingsResolved && uploadInfo) {
      badges.results = { label: "Run optimization", tone: "neutral" };
    }

    return badges;
  }, [
    uploadInfo,
    uploadError,
    busyAction,
    unmappedPairs.length,
    allMappingsResolved,
    optimization,
    settings.optimization_mode,
    settings.custom_families.length,
  ]);

  useEffect(() => {
    let cancelled = false;
    const timer = window.setInterval(async () => {
      try {
        await initApiBase();
        if (cancelled) return;
        const healthy = await checkHealth();
        if (cancelled) return;
        if (healthy) {
          setApiReady(true);
          setStatus("Ready");
          window.clearInterval(timer);
          void restoreExistingResults();
        }
      } catch (caught) {
        if (cancelled) return;
        setApiReady(false);
        setStatus(caught instanceof Error ? caught.message : "Starting engine...");
      }
    }, 1000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  async function restoreExistingResults() {
    try {
      const payload = await restoreResults();
      if (!payload) return;
      setRestoredOptimization(payload);
      setStatus("Previous results available");
    } catch {
      // Results are optional on first launch.
    }
  }

  function restorePreviousScenarioInternal(payload: OptimizationResponse) {
    setOptimization(payload);
    setDetailTab("insights");
    setActiveStage("results");
    setStatus("Previous results restored");
  }

  async function withBusy(action: Exclude<BusyAction, null>, callback: () => Promise<void>) {
    setBusyAction(action);
    setError(null);
    try {
      await callback();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
      setStatus("Action failed");
    } finally {
      setBusyAction(null);
    }
  }

  function consumeUploadResponse(payload: UploadResponse) {
    setUploadInfo(payload);
    setUnmappedPairs(payload.unmapped_pairs ?? []);
    setWorkbookPairs(payload.workbook_pairs ?? []);
  }

  async function uploadWorkbook(file: File) {
    if (!file.name.toLowerCase().endsWith(".xlsx")) {
      setUploadError("The file must be an .xlsx Excel workbook. Please check the file format and try again.");
      return;
    }

    setBusyAction("upload");
    setUploadError(null);
    setError(null);
    try {
      setStatus("Processing...");
      const payload = await uploadWorkbookRequest(file, settings.custom_families);
      consumeUploadResponse(payload);
      setUploadError(null);
      setTargetRows([]);
      setOptimization(null);
      setRestoredOptimization(null);
      setDetailTab("insights");
      // Always land on the Families step so the user sees the resolution surface and can
      // add custom families for target-mode planning even when the workbook is fully mapped.
      // If there are unmapped pairs, the step naturally pulls attention to them; if not, the
      // user can move to Plan with one click.
      const unresolved = payload.unmapped_pairs?.length ?? 0;
      setActiveStage("mappings");
      if (unresolved > 0) {
        setStatus(`${unresolved} unmapped role${unresolved === 1 ? "" : "s"} need attention`);
      } else {
        setStatus(`${payload.job_family_count} job families`);
      }
    } catch (caught) {
      setUploadError(caught instanceof Error ? caught.message : String(caught));
      setStatus("Validation failed");
    } finally {
      setBusyAction(null);
    }
  }

  async function applyMappingResolutions(updatedFamilies: CustomFamilySpec[]) {
    await withBusy("mappings", async () => {
      setSettings((current) => ({ ...current, custom_families: updatedFamilies }));
      setStatus("Re-processing workbook with updated mappings...");
      const payload = await reprocessWithMappingsRequest(updatedFamilies);
      consumeUploadResponse(payload);
      const unresolved = payload.unmapped_pairs?.length ?? 0;
      if (unresolved === 0) {
        setStatus(`${payload.job_family_count} job families`);
        setActiveStage("ready");
      } else {
        setStatus(`${unresolved} role${unresolved === 1 ? "" : "s"} still unmapped`);
      }
    });
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = "";
    if (file) void uploadWorkbook(file);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    const file = event.dataTransfer.files?.[0];
    if (file) void uploadWorkbook(file);
  }

  async function calculateTargetSplit() {
    // Internal helper used by runOptimization. Not bound to a user-visible action since
    // the "Policy Check" stage was removed; the min-headcount data is still surfaced in
    // the Decision view's audit table.
    setStatus("Checking minimum headcounts...");
    const payload = await calculateTargetSplitRequest(settings);
    setTargetRows(payload.rows);
  }

  async function runOptimization() {
    await withBusy("optimize", async () => {
      if (targetRows.length === 0) {
        const targetPayload = await calculateTargetSplitRequest(settings);
        setTargetRows(targetPayload.rows);
      }
      setStatus("Running optimization...");
      const payload = await runOptimizationRequest(settings);
      setOptimization(payload);
      setDetailTab("insights");
      setActiveStage("results");
      setStatus("Optimization complete");
    });
  }

  async function downloadResults() {
    try {
      window.location.href = await resultsExportUrl();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
      setStatus("Export failed");
    }
  }

  function updateSetting<K extends keyof Settings>(key: K, value: Settings[K]) {
    setSettings((current) => ({ ...current, [key]: value }));
  }

  function restorePreviousScenario() {
    if (!restoredOptimization) return;
    restorePreviousScenarioInternal(restoredOptimization);
  }

  function handleNavigate(target: AppStage) {
    // Pure navigation: just change the displayed stage. Data for later stages stays around
    // so the user can come back forward without re-running. Data is only cleared when the
    // user uploads a new workbook (which is an explicit reset).
    setActiveStage(target);
  }

  return (
    <AppShell
      stage={stage}
      reachableStages={reachableStages}
      stageBadges={stageBadges}
      apiReady={apiReady}
      status={status}
      busyAction={busyAction}
      canRun={Boolean(uploadInfo)}
      canResumeResults={Boolean(restoredOptimization) && !optimization}
      onUploadClick={() => fileInputRef.current?.click()}
      onRunOptimization={() => void runOptimization()}
      onResumeResults={restorePreviousScenario}
      onDownload={optimization ? () => void downloadResults() : undefined}
      onNavigate={handleNavigate}
    >
      {error ? (
        <div className="error-banner">
          <div className="error-banner-body">
            <strong>Something went wrong</strong>
            <p>{error}</p>
          </div>
          <button className="error-banner-dismiss" onClick={() => setError(null)} aria-label="Dismiss">×</button>
        </div>
      ) : null}

      {stage === "home" ? (
        <HomePage onStart={() => setActiveStage("upload")} />
      ) : stage === "results" && optimization ? (
        <ResultsDashboard
          optimization={optimization}
          targetRows={targetRows}
          detailTab={detailTab}
          onDetailTabChange={setDetailTab}
          debugEnabled={debugEnabled}
        />
      ) : stage === "mappings" && uploadInfo ? (
        <MappingResolveWorkspace
          uploadInfo={uploadInfo}
          unmappedPairs={unmappedPairs}
          workbookPairs={workbookPairs}
          customFamilies={settings.custom_families}
          busy={busyAction === "mappings"}
          onApply={(families) => void applyMappingResolutions(families)}
          onContinue={() => setActiveStage("ready")}
        />
      ) : (
        <>
          <UploadWorkspace
            apiReady={apiReady}
            busyAction={busyAction}
            uploadInfo={uploadInfo}
            uploadError={uploadError}
            isDragging={isDragging}
            fileInputRef={fileInputRef}
            onFileChange={handleFileChange}
            onDrop={handleDrop}
            onDragStateChange={setIsDragging}
            onCalculateTargetSplit={() => void calculateTargetSplit()}
            restoredResultsAvailable={Boolean(restoredOptimization)}
            onRestoreResults={restorePreviousScenario}
            debugEnabled={debugEnabled}
          />

          {stage !== "upload" && uploadInfo && allMappingsResolved ? (
            <ScenarioControls
              settings={settings}
              onUpdate={updateSetting}
              families={uploadInfo.families ?? []}
            />
          ) : null}

          {stage !== "upload" && uploadInfo && allMappingsResolved ? (
            <div className={`action-bar${stage === "ready" ? " action-bar--sticky" : ""}`}>
              <div className="action-bar-text">
                <p className="eyebrow">Ready</p>
                <h3>Run Optimization</h3>
              </div>
              <div className="action-bar-buttons">
                <button className="btn btn-primary" disabled={busyAction === "optimize"} onClick={() => void runOptimization()}>
                  {busyAction === "optimize" ? <><span className="spinner" /> Optimizing...</> : "Run Optimization"}
                </button>
                {optimization ? (
                  <button
                    className="btn btn-secondary"
                    onClick={() => setActiveStage("results")}
                    title="Open the latest optimization results"
                  >
                    Open last results
                  </button>
                ) : null}
              </div>
            </div>
          ) : null}
        </>
      )}

      {apiReady && debugEnabled && stage !== "home" ? <AssumptionsPanel /> : null}
    </AppShell>
  );
}
