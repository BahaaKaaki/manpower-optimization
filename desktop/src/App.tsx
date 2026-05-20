import { ChangeEvent, DragEvent, useEffect, useMemo, useRef, useState } from "react";

import {
  calculateTargetSplit as calculateTargetSplitRequest,
  checkHealth,
  initApiBase,
  resultsExportUrl,
  restoreResults,
  runOptimization as runOptimizationRequest,
  uploadWorkbook as uploadWorkbookRequest,
} from "./api/client";
import { AppShell, type StageBadge } from "./features/AppShell";
import { AssumptionsPanel } from "./features/AssumptionsPanel";
import { BUConfigurationPanel } from "./features/BUConfigurationPanel";
import { BUSelectionWorkspace, BUSINESS_UNITS } from "./features/BUSelectionWorkspace";
import { HomePage } from "./features/HomePage";
import { ModeSelectionWorkspace } from "./features/ModeSelectionWorkspace";
import { ResultsDashboard } from "./features/ResultsDashboard";
import { ScenarioControls } from "./features/ScenarioControls";
import { UploadWorkspace } from "./features/UploadWorkspace";
import type {
  ActivityProfession,
  AppStage,
  BUConfiguration,
  BusinessUnitCode,
  BusyAction,
  CustomFamilySpec,
  DetailTab,
  OptimizationResponse,
  Settings,
  UnmappedPair,
  UploadResponse,
} from "./types";

async function mergeActiveBUConfiguration(
  settings: Settings,
  activeBU: BusinessUnitCode | null,
): Promise<Settings> {
  if (!activeBU) return settings;
  const config = await persistGet<BUConfiguration | null>(`bu:${activeBU}:configuration`, null);
  if (!config) return settings;
  return {
    ...settings,
    saudi_cost_premium: config.saudi_cost_premium ?? settings.saudi_cost_premium,
    outsource_cost_discount:
      config.outsource_cost_discount !== undefined && config.outsource_cost_discount !== null
        ? config.outsource_cost_discount
        : settings.outsource_cost_discount,
    max_ratio_overrides: { ...settings.max_ratio_overrides, ...config.ratio_overrides },
    // The override fields below ride along as extra properties on the API request shape
    // (manpower_api/app.py:OptimizationSettingsRequest accepts them directly).
    outsourceability_overrides: config.outsourceability_overrides,
    activity_mapping: config.activity_mapping ?? {},
    profession_mapping: config.profession_mapping ?? {},
    job_family_mapping: config.job_family_mapping ?? {},
    driver_overrides: config.driver_overrides,
  } as Settings & {
    outsourceability_overrides: Record<string, string>;
    activity_mapping: Record<string, string>;
    profession_mapping: Record<string, string>;
    job_family_mapping: Record<string, string>;
    driver_overrides: Record<string, { activity: string; profession: string }[]>;
  };
}
import { persistGet, persistSet } from "./utils/persistence";

const defaultSettings: Settings = {
  enforce_saudization: true,
  saudization_rate: 0.3,
  can_reduce_current_saudi: false,
  // Default 1.0 = "Protect all current Saudis" (matches today's UX when the toggle is on).
  protect_current_saudi_percent: 1.0,
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
  // unmappedPairs surfaces from the upload response; with mappings now owned by the BU
  // Excel, encountering an unmapped pair is an error condition — the UploadWorkspace
  // hard-blocks until the user fixes the BU's Excel and re-uploads.
  const [unmappedPairs, setUnmappedPairs] = useState<UnmappedPair[]>([]);
  const [activeBU, setActiveBU] = useState<BusinessUnitCode | null>(null);
  const [configuringBU, setConfiguringBU] = useState<BusinessUnitCode | null>(null);
  // True once the active BU has at least one of profession/activity/job-family
  // mappings populated. When false, the Upload screen renders a hard-block
  // card instead of the drop zone. Polled when activeBU changes and after
  // the Configuration panel closes (the user may have just uploaded a config).
  const [isBUConfigured, setIsBUConfigured] = useState<boolean>(false);

  // Hydrate persisted custom_families on boot. Until the persistence layer reports back,
  // settings.custom_families is empty (the default). After hydration, any prior session's
  // user-defined families come back automatically.
  useEffect(() => {
    let cancelled = false;
    void persistGet<CustomFamilySpec[]>("custom_families", []).then((stored) => {
      if (cancelled || stored.length === 0) return;
      setSettings((current) => ({ ...current, custom_families: stored }));
    });
    void persistGet<BusinessUnitCode | null>("active_bu", null).then((stored) => {
      if (cancelled || !stored) return;
      setActiveBU(stored);
    });
    // MGIC's seed happens inside BUConfigurationPanel the first time it opens,
    // so the seed and the read don't race each other.
    return () => {
      cancelled = true;
    };
  }, []);

  // Persist custom_families on every change. Save is fire-and-forget; persistence is
  // best-effort, not on the critical path.
  useEffect(() => {
    void persistSet("custom_families", settings.custom_families);
  }, [settings.custom_families]);

  useEffect(() => {
    if (activeBU) void persistSet("active_bu", activeBU);
  }, [activeBU]);

  // Compute whether the active BU has any mapping data configured. Refresh
  // whenever the active BU changes OR whenever the Configuration panel closes
  // (the user may have just uploaded the BU's Excel and now is_empty is false).
  useEffect(() => {
    let cancelled = false;
    if (!activeBU) {
      setIsBUConfigured(false);
      return () => {
        cancelled = true;
      };
    }
    void persistGet<BUConfiguration | null>(`bu:${activeBU}:configuration`, null).then((stored) => {
      if (cancelled) return;
      const configured = Boolean(
        stored &&
          ((stored.profession_mapping && Object.keys(stored.profession_mapping).length > 0) ||
            (stored.activity_mapping && Object.keys(stored.activity_mapping).length > 0) ||
            (stored.job_family_mapping && Object.keys(stored.job_family_mapping).length > 0)),
      );
      setIsBUConfigured(configured);
    });
    return () => {
      cancelled = true;
    };
  }, [activeBU, configuringBU]);


  // With BU Excel owning all mappings, the workflow has no separate "Mappings" stage.
  // If the uploaded payroll has unmapped (activity, profession) pairs, UploadWorkspace
  // hard-blocks until the user fixes the BU's Excel — we don't gate downstream stages
  // here, but `uploadCleared` reflects whether the upload landed without unmapped pairs.
  const uploadCleared = uploadInfo !== null && unmappedPairs.length === 0;

  const reachableStages = useMemo<Set<AppStage>>(() => {
    const reachable = new Set<AppStage>(["home", "bu-selection"]);
    if (activeBU) reachable.add("upload");
    if (uploadCleared) {
      reachable.add("mode");
      reachable.add("ready");
    }
    if (uploadCleared && optimization) reachable.add("results");
    return reachable;
  }, [activeBU, uploadCleared, optimization]);

  // Stage to display = user's selection when its data is still present, otherwise the
  // highest reachable stage. Lets the user navigate freely between any stage that has
  // data without destroying later stages on backwards navigation.
  const stage: AppStage = useMemo(() => {
    if (reachableStages.has(activeStage)) return activeStage;
    if (uploadCleared && optimization) return "results";
    if (uploadCleared) return "ready";
    if (activeBU) return "upload";
    return "bu-selection";
  }, [activeStage, reachableStages, optimization, uploadCleared, activeBU]);

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

    // When uploadInfo is present but unmapped pairs exist, the upload step badge
    // already reflects the trouble via tone="danger" set above. No separate Mappings
    // badge anymore.
    if (uploadInfo && unmappedPairs.length > 0) {
      badges.upload = { label: `${unmappedPairs.length} unmapped`, tone: "danger" };
    }

    if (activeBU) {
      const bu = BUSINESS_UNITS.find((b) => b.code === activeBU);
      if (bu) badges["bu-selection"] = { label: bu.code.replace(/_/g, " "), tone: "positive" };
    } else {
      badges["bu-selection"] = { label: "Select a BU", tone: "warning" };
    }

    if (uploadCleared) {
      badges.mode = {
        label: settings.optimization_mode === "target" ? "Target plan" : "Current",
        tone: settings.optimization_mode === "target" ? "info" : "neutral",
      };
      badges.ready = {
        label: settings.optimization_mode === "target" ? "Target plan" : "Current",
        tone: settings.optimization_mode === "target" ? "info" : "neutral",
      };
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
    } else if (uploadCleared) {
      badges.results = { label: "Run optimization", tone: "neutral" };
    }

    return badges;
  }, [
    uploadInfo,
    uploadError,
    busyAction,
    unmappedPairs.length,
    uploadCleared,
    optimization,
    settings.optimization_mode,
    settings.custom_families.length,
    activeBU,
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
      // Pull the active BU's saved configuration so its mappings (profession, activity,
      // job family) are applied to the payroll on the first pass — no separate Mappings
      // stage anymore.
      const buConfiguration = activeBU
        ? await persistGet<BUConfiguration | null>(`bu:${activeBU}:configuration`, null)
        : null;
      const payload = await uploadWorkbookRequest(file, settings.custom_families, buConfiguration);
      consumeUploadResponse(payload);
      setUploadError(null);
      setTargetRows([]);
      setOptimization(null);
      setRestoredOptimization(null);
      setDetailTab("insights");
      const unresolved = payload.unmapped_pairs?.length ?? 0;
      if (unresolved > 0) {
        // Stay on the Upload stage; UploadWorkspace renders an alert pointing the user
        // back to the BU's Excel to add the missing mappings.
        setStatus(`${unresolved} unmapped role${unresolved === 1 ? "" : "s"} - update BU Excel`);
      } else {
        setActiveStage("mode");
        setStatus(`${payload.job_family_count} job families`);
      }
    } catch (caught) {
      setUploadError(caught instanceof Error ? caught.message : String(caught));
      setStatus("Validation failed");
    } finally {
      setBusyAction(null);
    }
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
      const settingsWithBU = await mergeActiveBUConfiguration(settings, activeBU);
      if (targetRows.length === 0) {
        const targetPayload = await calculateTargetSplitRequest(settingsWithBU);
        setTargetRows(targetPayload.rows);
      }
      setStatus("Running optimization...");
      const payload = await runOptimizationRequest(settingsWithBU);
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
      canRun={Boolean(uploadInfo)}
      canResumeResults={Boolean(restoredOptimization) && !optimization}
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
        <HomePage onStart={() => setActiveStage("bu-selection")} />
      ) : stage === "bu-selection" && configuringBU ? (
        <BUConfigurationPanel
          buCode={configuringBU}
          buName={BUSINESS_UNITS.find((b) => b.code === configuringBU)?.name ?? configuringBU}
          onClose={() => setConfiguringBU(null)}
          onSaved={(code) => {
            // Saving sets this BU as the active one and advances straight to upload.
            // The Configuration save is the "use it" gesture, so the user doesn't have
            // to click the tile a second time after configuring.
            setActiveBU(code);
            setConfiguringBU(null);
            setActiveStage("upload");
          }}
        />
      ) : stage === "bu-selection" ? (
        <BUSelectionWorkspace
          activeBU={activeBU}
          onUse={(code) => {
            setActiveBU(code);
            setActiveStage("upload");
          }}
          onConfigure={(code) => setConfiguringBU(code)}
        />
      ) : stage === "mode" && uploadInfo ? (
        <ModeSelectionWorkspace settings={settings} onUpdate={updateSetting} />
      ) : stage === "results" && optimization ? (
        <ResultsDashboard
          optimization={optimization}
          targetRows={targetRows}
          detailTab={detailTab}
          onDetailTabChange={setDetailTab}
          debugEnabled={debugEnabled}
        />
      ) : (
        <>
          {stage === "upload" ? (
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
              unmappedPairs={unmappedPairs}
              activeBUName={activeBU ? (BUSINESS_UNITS.find((b) => b.code === activeBU)?.name ?? activeBU) : null}
              isBUConfigured={isBUConfigured}
              onOpenBUConfiguration={() => {
                if (activeBU) {
                  setConfiguringBU(activeBU);
                  setActiveStage("bu-selection");
                }
              }}
            />
          ) : null}

          {stage !== "upload" && uploadCleared ? (
            <ScenarioControls
              settings={settings}
              onUpdate={updateSetting}
              families={uploadInfo.families ?? []}
            />
          ) : null}

          {stage !== "upload" && uploadCleared ? (
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
