import { useEffect, useRef, useState } from "react";

import {
  exportBUConfiguration,
  fetchAssumptionDefaults,
  importBUConfiguration,
  type AssumptionDefaults,
} from "../api/client";
import type { BUConfiguration, BusinessUnitCode } from "../types";
import { persistGet, persistSet } from "../utils/persistence";

type Props = {
  buCode: BusinessUnitCode;
  buName: string;
  onClose: () => void;
  onSaved?: (code: BusinessUnitCode) => void;
};

function configKey(code: BusinessUnitCode) {
  return `bu:${code}:configuration`;
}

const EMPTY_CONFIG: BUConfiguration = {
  outsourceability_overrides: {},
  ratio_overrides: {},
  driver_overrides: {},
  saudi_cost_premium: null,
  outsource_cost_discount: null,
};

export function BUConfigurationPanel({ buCode, buName, onClose, onSaved }: Props) {
  const [defaults, setDefaults] = useState<AssumptionDefaults | null>(null);
  const [config, setConfig] = useState<BUConfiguration>(EMPTY_CONFIG);
  const [hasSavedConfig, setHasSavedConfig] = useState<boolean>(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [importErrors, setImportErrors] = useState<string[]>([]);
  const [importStatus, setImportStatus] = useState<string | null>(null);
  const [isDraggingFile, setIsDraggingFile] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  function handleDroppedFile(file: File | undefined) {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".xlsx")) {
      setImportErrors(["Only .xlsx files are accepted."]);
      setImportStatus("Wrong file type.");
      return;
    }
    void handleUploadFile(file);
  }

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      const stored = await persistGet<BUConfiguration | null>(configKey(buCode), null);
      if (cancelled) return;

      // Defaults are needed both for the "valid values" reference (Excel side) and as the
      // seed for MGIC's first-open. Fetch in parallel; on failure the panel still renders
      // with whatever saved state we have.
      let fetchedDefaults: AssumptionDefaults | null = null;
      try {
        fetchedDefaults = await fetchAssumptionDefaults();
        if (cancelled) return;
        setDefaults(fetchedDefaults);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      }

      if (stored) {
        setConfig(stored);
        setHasSavedConfig(true);
        return;
      }

      // MGIC ships preconfigured with the tool's canonical defaults. If nothing is saved
      // yet, seed it here so the download Excel comes back pre-filled and the user can
      // just edit whichever rows they want to change. Other BUs stay empty until the
      // user uploads a configuration for them.
      if (buCode === "MGIC" && fetchedDefaults) {
        const seeded: BUConfiguration = {
          outsourceability_overrides: { ...fetchedDefaults.outsourceability },
          ratio_overrides: { ...fetchedDefaults.max_ratios },
          driver_overrides: { ...fetchedDefaults.drivers },
          saudi_cost_premium: 1.10,
          outsource_cost_discount: null,
        };
        await persistSet(configKey(buCode), seeded);
        if (cancelled) return;
        setConfig(seeded);
        setHasSavedConfig(true);
        return;
      }

      setConfig(EMPTY_CONFIG);
      setHasSavedConfig(false);
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [buCode]);

  async function saveAll() {
    setSaving(true);
    try {
      await persistSet(configKey(buCode), config);
      onSaved?.(buCode);
      onClose();
    } finally {
      setSaving(false);
    }
  }

  async function handleDownload() {
    try {
      await exportBUConfiguration({
        bu_code: buCode,
        bu_name: buName,
        configuration: config,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleUploadFile(file: File) {
    setImportErrors([]);
    setImportStatus("Reading file…");
    try {
      const result = await importBUConfiguration(file);
      if (result.errors.length > 0) {
        setImportErrors(result.errors);
        setImportStatus(`Found ${result.errors.length} issue${result.errors.length === 1 ? "" : "s"}. Please fix the values shown below and try again.`);
        return;
      }
      setConfig(result.configuration);
      setHasSavedConfig(true);
      setImportStatus("Values updated. Review below and click Use this BU when ready.");
    } catch (err) {
      setImportErrors([err instanceof Error ? err.message : String(err)]);
      setImportStatus("Upload failed.");
    }
  }

  if (error) {
    return (
      <div className="bu-config-panel">
        <p className="bu-config-error">Could not load configuration defaults: {error}</p>
        <button className="btn btn-secondary" onClick={onClose}>Back to BU Selection</button>
      </div>
    );
  }

  if (!defaults) {
    return (
      <div className="bu-config-panel">
        <p className="bu-config-loading">Loading configuration defaults…</p>
      </div>
    );
  }

  const outsourceabilityRows = hasSavedConfig
    ? Object.entries(config.outsourceability_overrides).sort(([a], [b]) => a.localeCompare(b))
    : [];
  const ratioRows = hasSavedConfig
    ? Object.entries(config.ratio_overrides).sort(([a], [b]) => a.localeCompare(b))
    : [];

  return (
    <div className="bu-config-panel">
      <div className="bu-config-head">
        <div>
          <span className="bu-config-eyebrow">Configuration</span>
          <h2>{buName}</h2>
          <p className="bu-config-hint">
            {hasSavedConfig ? (
              <>
                Review {buName}'s configuration below. To change any value, download the
                Excel, edit it, and upload it back. Click <strong>Use this BU</strong> when
                you're ready to continue.
              </>
            ) : (
              <>
                {buName} hasn't been set up yet. Download the starter Excel, fill it in for
                this Business Unit, then upload it back to activate.
              </>
            )}
          </p>
        </div>
        <div className="bu-config-actions">
          <button className="btn btn-secondary" onClick={onClose} disabled={saving}>
            Back
          </button>
          <button
            className="btn btn-primary"
            onClick={() => void saveAll()}
            disabled={saving || !hasSavedConfig}
            title={!hasSavedConfig ? "Upload a configuration Excel first." : undefined}
          >
            {saving ? "Saving…" : "Use this BU"}
          </button>
        </div>
      </div>

      <section className="bu-config-section bu-config-io">
        <div className="bu-config-io-head">
          <span className="bu-config-io-eyebrow">Configuration via Excel</span>
          <h3>Edit values in Excel, upload to apply</h3>
        </div>

        <div className="bu-config-io-grid">
          {/* Step 1: Download */}
          <div className="bu-config-io-card bu-config-io-card--download">
            <div className="bu-config-io-card-step">Step 1</div>
            <div className="bu-config-io-card-icon" aria-hidden>
              <svg viewBox="0 0 48 48" fill="none">
                <rect x="8" y="6" width="28" height="36" rx="3" stroke="currentColor" strokeWidth="1.8" />
                <path d="M8 14h28M8 22h28M8 30h28" stroke="currentColor" strokeWidth="1.2" opacity="0.4" />
                <circle cx="38" cy="36" r="9" fill="#fff" stroke="currentColor" strokeWidth="1.8" />
                <path
                  d="M38 31v10m0 0l-3.5-3.5M38 41l3.5-3.5"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
            <div className="bu-config-io-card-body">
              <h4 className="bu-config-io-card-title">
                {hasSavedConfig ? "Download current configuration" : "Download starter Excel"}
              </h4>
              <p className="bu-config-io-card-desc">
                {hasSavedConfig
                  ? `Pre-filled with ${buName}'s current values. Edit any row you want to change, save, then upload it back.`
                  : `Canonical job families and supervisors listed for reference. Fill the Value column for the rows that apply to ${buName}.`}
              </p>
            </div>
            <button
              type="button"
              className="bu-config-io-card-btn bu-config-io-card-btn--download"
              onClick={() => void handleDownload()}
            >
              <svg viewBox="0 0 16 16" fill="none" aria-hidden>
                <path
                  d="M8 2v9m0 0l-3-3m3 3l3-3M3 14h10"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              Download Excel
            </button>
          </div>

          {/* Step 2: Upload (drag and drop) */}
          <div
            className={`bu-config-io-card bu-config-io-card--upload${
              isDraggingFile ? " bu-config-io-card--dragging" : ""
            }`}
            role="button"
            tabIndex={0}
            onClick={() => fileInputRef.current?.click()}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") fileInputRef.current?.click();
            }}
            onDragEnter={(e) => {
              e.preventDefault();
              setIsDraggingFile(true);
            }}
            onDragOver={(e) => {
              e.preventDefault();
            }}
            onDragLeave={() => setIsDraggingFile(false)}
            onDrop={(e) => {
              e.preventDefault();
              setIsDraggingFile(false);
              handleDroppedFile(e.dataTransfer.files?.[0]);
            }}
          >
            <div className="bu-config-io-card-step">Step 2</div>
            <div className="bu-config-io-card-icon" aria-hidden>
              <svg viewBox="0 0 48 48" fill="none">
                <path
                  d="M16 30L24 22L32 30M24 22V40"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d="M38 20c3.31 0 6 2.69 6 6 0 2.97-2.16 5.44-5 5.92M10 20c-3.31 0-6 2.69-6 6 0 2.97 2.16 5.44 5 5.92"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                />
                <path
                  d="M14 22c0-5.52 4.48-10 10-10s10 4.48 10 10"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                />
              </svg>
            </div>
            <div className="bu-config-io-card-body">
              <h4 className="bu-config-io-card-title">
                {isDraggingFile ? "Drop your file" : "Upload edited Excel"}
              </h4>
              <p className="bu-config-io-card-desc">
                Drop your <code>.xlsx</code> file here, or click anywhere in this card to browse.
              </p>
            </div>
            <span className="bu-config-io-card-btn bu-config-io-card-btn--upload">
              <svg viewBox="0 0 16 16" fill="none" aria-hidden>
                <path
                  d="M8 14V5m0 0l-3 3m3-3l3 3M3 2h10"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              Choose file or drop here
            </span>
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx"
              hidden
              onChange={(e) => {
                const file = e.currentTarget.files?.[0];
                e.currentTarget.value = "";
                handleDroppedFile(file);
              }}
            />
          </div>
        </div>

        {importStatus ? (
          <div
            className={`bu-config-import-status${
              importErrors.length > 0 ? " bu-config-import-status--error" : " bu-config-import-status--ok"
            }`}
          >
            <strong>{importStatus}</strong>
            {importErrors.length > 0 ? (
              <ul>
                {importErrors.map((msg, i) => (
                  <li key={i}>{msg}</li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}
      </section>

      {!hasSavedConfig ? (
        <section className="bu-config-section bu-config-empty">
          <p>
            <strong>No configuration yet.</strong> Download a starter Excel above, fill it in,
            then upload it back. The values will appear here once the file is valid.
          </p>
        </section>
      ) : (
        <>
          {/* Sticky in-panel navigation. Tells the user there are 3 sections below
              even before they scroll, and lets them jump directly to each one. */}
          <nav className="bu-config-toc" aria-label="Configuration sections">
            <span className="bu-config-toc-label">Sections</span>
            <a href="#bu-config-outsourceability" className="bu-config-toc-chip">
              <span className="bu-config-toc-num">1</span>
              Outsourceability
              <span className="bu-config-toc-count">{outsourceabilityRows.length}</span>
            </a>
            <a href="#bu-config-ratios" className="bu-config-toc-chip">
              <span className="bu-config-toc-num">2</span>
              Ratios
              <span className="bu-config-toc-count">{ratioRows.length}</span>
            </a>
          </nav>

          <section className="bu-config-section" id="bu-config-outsourceability">
            <h3>
              <span className="bu-config-section-num">1</span>
              Outsourceability per job family
              <span className="bu-config-section-count">{outsourceabilityRows.length} families</span>
            </h3>
            <table className="bu-config-table">
              <thead>
                <tr>
                  <th>Job family</th>
                  <th>Value</th>
                </tr>
              </thead>
              <tbody>
                {outsourceabilityRows.length === 0 ? (
                  <tr>
                    <td colSpan={2} className="bu-config-empty-row">
                      No job families configured.
                    </td>
                  </tr>
                ) : (
                  outsourceabilityRows.map(([family, value]) => (
                    <tr key={family}>
                      <td>{family}</td>
                      <td className="bu-config-active">{value}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </section>

          <section className="bu-config-section" id="bu-config-ratios">
            <h3>
              <span className="bu-config-section-num">2</span>
              Supervisor : worker ratios
              <span className="bu-config-section-count">{ratioRows.length} supervisors</span>
            </h3>
            <table className="bu-config-table">
              <thead>
                <tr>
                  <th>Supervisor family</th>
                  <th>Value</th>
                </tr>
              </thead>
              <tbody>
                {ratioRows.length === 0 ? (
                  <tr>
                    <td colSpan={2} className="bu-config-empty-row">
                      No ratios configured.
                    </td>
                  </tr>
                ) : (
                  ratioRows.map(([family, value]) => (
                    <tr key={family}>
                      <td>{family}</td>
                      <td className="bu-config-active">{value}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </section>

        </>
      )}
    </div>
  );
}
