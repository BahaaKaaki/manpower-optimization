import type {
  AssumptionsCatalog,
  CustomFamilySpec,
  OptimizationResponse,
  Settings,
  TargetSplitResponse,
  UploadResponse,
} from "../types";

type TauriInternals = {
  invoke?: unknown;
};

declare global {
  interface Window {
    __TAURI_INTERNALS__?: TauriInternals;
  }
}

/**
 * API origin for fetch calls.
 * - Development (Vite): default "" so requests hit the dev server and `vite.config.ts` proxies to FastAPI.
 * - Production web (Docker/Azure): build with `VITE_API_BASE=""` so paths are same-origin.
 * - Packaged desktop (Tauri): Rust picks a per-process localhost port and exposes it via invoke.
 */
function resolveStaticApiBase(): string {
  const raw = import.meta.env.VITE_API_BASE;
  if (raw !== undefined) return raw;
  return "";
}

function isTauriRuntime(): boolean {
  return typeof window !== "undefined" && typeof window.__TAURI_INTERNALS__?.invoke === "function";
}

let apiBasePromise: Promise<string> | null = null;

export function initApiBase(): Promise<string> {
  apiBasePromise ??= resolveApiBase().catch((error) => {
    apiBasePromise = null;
    throw error;
  });
  return apiBasePromise;
}

function normalizeApiBase(base: string): string {
  return base.replace(/\/+$/, "");
}

async function resolveApiBase(): Promise<string> {
  if (import.meta.env.DEV) return "";

  if (isTauriRuntime()) {
    const { invoke } = await import("@tauri-apps/api/core");
    return normalizeApiBase(await invoke<string>("get_manpower_api_base"));
  }

  return normalizeApiBase(resolveStaticApiBase());
}

export async function getApiBase(): Promise<string> {
  return initApiBase();
}

async function parseResponse<T>(response: Response, fallbackMessage: string): Promise<T> {
  if (!response.ok) {
    let detail = fallbackMessage;
    try {
      const payload = await response.json();
      detail = payload.detail || fallbackMessage;
    } catch {
      // Preserve the fallback when the server returns non-JSON errors.
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export async function checkHealth() {
  const apiBase = await getApiBase();
  const response = await fetch(`${apiBase}/health`);
  return response.ok;
}

export async function fetchAssumptions() {
  const apiBase = await getApiBase();
  const response = await fetch(`${apiBase}/assumptions`);
  return parseResponse<AssumptionsCatalog>(response, "Failed to load assumptions catalog.");
}

export type AssumptionDefaults = {
  outsourceability: Record<string, string>;
  max_ratios: Record<string, string>;
  drivers: Record<string, { activity: string; profession: string }[]>;
  profession_mapping: Record<string, string>;
  activity_mapping: Record<string, string>;
  job_family_mapping: Record<string, string>;
};

export async function fetchAssumptionDefaults() {
  const apiBase = await getApiBase();
  const response = await fetch(`${apiBase}/assumptions/defaults`);
  return parseResponse<AssumptionDefaults>(response, "Failed to load configuration defaults.");
}

/**
 * Trigger a browser download of the current BU configuration as XLSX. POSTs the
 * payload so the user gets a workbook reflecting their unsaved edits too.
 */
export async function exportBUConfiguration(payload: {
  bu_code: string;
  bu_name?: string;
  configuration: unknown;
}): Promise<void> {
  const apiBase = await getApiBase();
  const response = await fetch(`${apiBase}/bu/configuration/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Export failed: ${response.status}`);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${payload.bu_code || "manpower-bu"}_configuration.xlsx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export type BUConfigurationImportResponse = {
  configuration: {
    outsourceability_overrides: Record<string, string>;
    ratio_overrides: Record<string, string>;
    driver_overrides: Record<string, { activity: string; profession: string }[]>;
    saudi_cost_premium: number | null;
    outsource_cost_discount: number | null;
  };
  errors: string[];
};

export async function importBUConfiguration(file: File): Promise<BUConfigurationImportResponse> {
  const apiBase = await getApiBase();
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${apiBase}/bu/configuration/import`, {
    method: "POST",
    body: form,
  });
  return parseResponse<BUConfigurationImportResponse>(response, "Import failed.");
}

export async function uploadWorkbook(
  file: File,
  customFamilies: CustomFamilySpec[] = [],
  buConfiguration: unknown = null,
) {
  const formData = new FormData();
  formData.append("file", file);
  if (customFamilies.length > 0) {
    formData.append("custom_families", JSON.stringify(customFamilies));
  }
  if (buConfiguration && typeof buConfiguration === "object") {
    formData.append("bu_configuration", JSON.stringify(buConfiguration));
  }
  const apiBase = await getApiBase();
  const response = await fetch(`${apiBase}/workbooks/upload`, {
    method: "POST",
    body: formData,
  });
  return parseResponse<UploadResponse>(response, "Workbook upload failed.");
}

export async function reprocessWithMappings(
  customFamilies: CustomFamilySpec[],
  payrollPairOverrides: Record<string, string> = {},
) {
  const apiBase = await getApiBase();
  const response = await fetch(`${apiBase}/workbooks/reprocess`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      custom_families: customFamilies,
      payroll_pair_overrides: payrollPairOverrides,
    }),
  });
  return parseResponse<UploadResponse>(response, "Reprocessing with new mappings failed.");
}

export async function calculateTargetSplit(settings: Settings) {
  const apiBase = await getApiBase();
  const response = await fetch(`${apiBase}/optimization/target-split`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
  return parseResponse<TargetSplitResponse>(response, "Target split calculation failed.");
}

export async function runOptimization(settings: Settings) {
  const apiBase = await getApiBase();
  const response = await fetch(`${apiBase}/optimization/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
  return parseResponse<OptimizationResponse>(response, "Optimization failed.");
}

export async function restoreResults() {
  const apiBase = await getApiBase();
  const response = await fetch(`${apiBase}/optimization/results`);
  if (response.status === 204) return null;
  if (!response.ok) return null;
  return response.json() as Promise<OptimizationResponse>;
}

export async function resultsExportUrl() {
  const apiBase = await getApiBase();
  return `${apiBase}/exports/results.xlsx`;
}
