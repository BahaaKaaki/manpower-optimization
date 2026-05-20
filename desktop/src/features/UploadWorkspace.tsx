import type { DragEvent } from "react";

import { MetricCard } from "../components/MetricCard";
import { SectionHeader } from "../components/SectionHeader";
import type { BusyAction, UnmappedPair, UploadResponse } from "../types";
import { formatNumber } from "../utils/format";

type UploadWorkspaceProps = {
  apiReady: boolean;
  busyAction: BusyAction;
  uploadInfo: UploadResponse | null;
  uploadError: string | null;
  isDragging: boolean;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  onFileChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onDrop: (event: DragEvent<HTMLDivElement>) => void;
  onDragStateChange: (isDragging: boolean) => void;
  onCalculateTargetSplit: () => void;
  restoredResultsAvailable: boolean;
  onRestoreResults: () => void;
  debugEnabled: boolean;
  unmappedPairs: UnmappedPair[];
  activeBUName: string | null;
  onOpenBUConfiguration: () => void;
};

function ValidationFeedback({ error, onRetry }: { error: string; onRetry: () => void }) {
  const isMissingSheets = error.toLowerCase().includes("missing required sheet");
  const isMissingColumns = error.toLowerCase().includes("missing required column");
  const isInvalidFile = error.toLowerCase().includes("could not read");

  const title = isInvalidFile
    ? "Invalid file format"
    : isMissingSheets
      ? "Workbook structure issue"
      : "Missing data fields";

  const subtitle = isInvalidFile
    ? "The file could not be read as an Excel workbook"
    : isMissingSheets
      ? "Required worksheet tabs are missing from the file"
      : "Some required columns were not found in the data";

  return (
    <div className="validation-card">
      <div className="validation-header">
        <div className="validation-header-icon">
          <svg viewBox="0 0 20 20" fill="none">
            <path d="M10 6v4m0 4h.01M3.07 16h13.86c1.1 0 1.79-1.18 1.25-2.13L11.25 3.23c-.55-.95-1.95-.95-2.5 0L1.82 13.87c-.54.95.16 2.13 1.25 2.13z" stroke="#f59e0b" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
        <div className="validation-header-text">
          <h3>{title}</h3>
          <p>{subtitle}</p>
        </div>
      </div>

      <div className="validation-body">
        <p className="validation-message">{error}</p>

        <div className="validation-checklist">
          <span className="validation-checklist-label">Validation checks</span>

          <div className={`validation-check ${isInvalidFile ? "check-fail" : "check-pass"}`}>
            <span className="validation-check-icon">{isInvalidFile ? "×" : "✓"}</span>
            Valid .xlsx Excel format
          </div>

          <div className={`validation-check ${isMissingSheets || isInvalidFile ? "check-fail" : "check-pass"}`}>
            <span className="validation-check-icon">{isMissingSheets || isInvalidFile ? "×" : "✓"}</span>
            Contains required sheets (Inhouse, Subcontractor)
          </div>

          {!isInvalidFile && !isMissingSheets && (
            <div className={`validation-check ${isMissingColumns ? "check-fail" : "check-pass"}`}>
              <span className="validation-check-icon">{isMissingColumns ? "×" : "✓"}</span>
              Required columns present in each sheet
            </div>
          )}
        </div>
      </div>

      <div className="validation-footer">
        <span className="validation-footer-hint">
          <strong>Tip:</strong> Check the workbook template for the expected structure
        </span>
        <button className="btn btn-primary" onClick={onRetry}>
          Upload corrected file
        </button>
      </div>
    </div>
  );
}

export function UploadWorkspace({
  apiReady,
  busyAction,
  uploadInfo,
  uploadError,
  isDragging,
  fileInputRef,
  onFileChange,
  onDrop,
  onDragStateChange,
  onCalculateTargetSplit,
  restoredResultsAvailable,
  onRestoreResults,
  debugEnabled,
  unmappedPairs,
  activeBUName,
  onOpenBUConfiguration,
}: UploadWorkspaceProps) {
  const totalWorkforce = (uploadInfo?.inhouse_count ?? 0) + (uploadInfo?.subcontractor_count ?? 0);
  const modelRows = uploadInfo?.model_input_count ?? uploadInfo?.model_input?.length ?? 0;
  const hasUnmapped = unmappedPairs.length > 0;

  if (!uploadInfo) {
    return (
      <section className="upload-stage">
        {restoredResultsAvailable ? (
          <div className="resume-banner">
            <div className="resume-banner-text">
              <strong>Previous scenario available</strong>
              <p>Resume the last completed optimization, or upload a new workbook for a fresh scenario.</p>
            </div>
            <button className="btn btn-secondary btn-sm" onClick={onRestoreResults}>Resume results</button>
          </div>
        ) : null}

        <div className="upload-hero-card">
          <div className="upload-hero-intro">
            <h2>Upload Workbook</h2>
          </div>

          <input ref={fileInputRef} className="file-input" type="file" accept=".xlsx" onChange={onFileChange} />

          {uploadError ? (
            <ValidationFeedback error={uploadError} onRetry={() => fileInputRef.current?.click()} />
          ) : (
            <div
              className={`upload-zone ${isDragging ? "dragging" : ""}`}
              role="button"
              tabIndex={0}
              onClick={() => fileInputRef.current?.click()}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") fileInputRef.current?.click();
              }}
              onDragEnter={(event) => {
                event.preventDefault();
                onDragStateChange(true);
              }}
              onDragOver={(event) => event.preventDefault()}
              onDragLeave={() => onDragStateChange(false)}
              onDrop={onDrop}
            >
              <div className="upload-zone-icon">XLSX</div>
              <span className="upload-zone-title">
                {busyAction === "upload" ? "Processing workbook..." : "Drop workbook here or click to browse"}
              </span>
              <span className="upload-zone-subtitle">
                Upload In-house and Outsourced Employees Payroll in one Excel workbook
              </span>
              <button
                className="btn btn-primary"
                type="button"
                disabled={!apiReady || busyAction === "upload"}
                onClick={(event) => {
                  event.stopPropagation();
                  fileInputRef.current?.click();
                }}
              >
                {busyAction === "upload" ? <><span className="spinner" /> Processing...</> : "Browse files"}
              </button>
            </div>
          )}

        </div>
      </section>
    );
  }

  if (hasUnmapped) {
    return (
      <section className="upload-stage">
        <input ref={fileInputRef} className="file-input" type="file" accept=".xlsx" onChange={onFileChange} />
        <div className="unmapped-block">
          <div className="unmapped-block-head">
            <div className="unmapped-block-icon" aria-hidden>
              <svg viewBox="0 0 24 24" fill="none">
                <path
                  d="M12 8v5m0 4h.01M3.07 19h17.86c1.1 0 1.79-1.18 1.25-2.13L13.25 4.23c-.55-.95-1.95-.95-2.5 0L1.82 16.87c-.54.95.16 2.13 1.25 2.13z"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
            <div>
              <h3>This payroll uses {unmappedPairs.length} role{unmappedPairs.length === 1 ? "" : "s"} {activeBUName ?? "this BU"} hasn't configured yet</h3>
              <p>
                Add the missing rows to <strong>{activeBUName ?? "the BU"}</strong>'s configuration
                Excel — in the <strong>Job Families</strong> sheet (and the <strong>Profession Mapping</strong>
                or <strong>Activity Mapping</strong> sheets if the raw values differ from the standard
                ones). Then upload the updated Excel and try this payroll again.
              </p>
            </div>
          </div>
          <table className="unmapped-table">
            <thead>
              <tr>
                <th>Activity (from payroll)</th>
                <th>Profession (from payroll)</th>
                <th>Rows</th>
              </tr>
            </thead>
            <tbody>
              {unmappedPairs.slice(0, 20).map((pair) => (
                <tr key={`${pair.activity}|${pair.profession}`}>
                  <td>{pair.activity}</td>
                  <td>{pair.profession}</td>
                  <td>{pair.count}</td>
                </tr>
              ))}
              {unmappedPairs.length > 20 ? (
                <tr>
                  <td colSpan={3} className="unmapped-table-overflow">
                    + {unmappedPairs.length - 20} more
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
          <div className="unmapped-actions">
            <button className="btn btn-primary" type="button" onClick={onOpenBUConfiguration}>
              Open BU Configuration
            </button>
            <button
              className="btn btn-secondary"
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={!apiReady || busyAction === "upload"}
            >
              {busyAction === "upload" ? <><span className="spinner" /> Processing...</> : "Upload a different payroll"}
            </button>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className={`baseline-grid${debugEnabled ? "" : " baseline-grid--single"}`}>
      <div className="card">
        <SectionHeader
          eyebrow="Data Loaded"
          title={uploadInfo.filename ?? "Workbook"}
        />

        <input ref={fileInputRef} className="file-input" type="file" accept=".xlsx" onChange={onFileChange} />

        <div className="data-health-total">
          <MetricCard label="Total workforce" value={formatNumber(totalWorkforce, 0)} tone="accent" />
        </div>
        <div className="data-health-grid data-health-grid--triple">
          <MetricCard label="In-house" value={formatNumber(uploadInfo.inhouse_count, 0)} />
          <MetricCard label="Outsourced" value={formatNumber(uploadInfo.subcontractor_count, 0)} />
          <MetricCard label="Job families" value={formatNumber(uploadInfo.job_family_count, 0)} />
        </div>

        <div className="data-health-actions">
          <button
            className="btn btn-secondary btn-sm"
            type="button"
            disabled={!apiReady || busyAction === "upload"}
            onClick={() => fileInputRef.current?.click()}
          >
            {busyAction === "upload" ? <><span className="spinner" /> Processing...</> : "Replace workbook"}
          </button>
        </div>
      </div>

      {debugEnabled ? (
      <div className="card">
        <SectionHeader
          eyebrow="Debug"
          title="Detected signals"
          copy="These fields determine whether optimization uses service-fee and tenure-aware logic."
        />
        <div className="inspector-list">
          <div className="inspector-row">
            <span>Workbook</span>
            <strong>{uploadInfo.filename}</strong>
          </div>
          <div className="inspector-row">
            <span>Service fee column</span>
            <strong>{uploadInfo.service_fee_column || "Not detected"}</strong>
          </div>
          <div className="inspector-row">
            <span>Tenure source</span>
            <strong>{uploadInfo.tenure_source_column || "Not detected"}</strong>
          </div>
          <div className="inspector-row">
            <span>Model rows</span>
            <strong>{formatNumber(modelRows, 0)}</strong>
          </div>
        </div>
        <div style={{ marginTop: "16px" }}>
          <button className="btn btn-primary" disabled={busyAction === "target"} onClick={onCalculateTargetSplit}>
            {busyAction === "target" ? <><span className="spinner" /> Calculating...</> : "Calculate target split"}
          </button>
        </div>
      </div>
      ) : null}
    </section>
  );
}
