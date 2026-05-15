import { useMemo, useState } from "react";

import { DataTable, type ColumnDef } from "../components/DataTable";
import { DonutChart } from "../components/DonutChart";
import type { DetailTab, OptimizationResponse } from "../types";
import {
  formatCompactCurrency,
  formatCurrency,
  formatNumber,
  formatPercent,
  getRowNumber,
  getString,
  safeSavingsPercent,
  toNumber,
} from "../utils/format";

const saudiFlagUrl = new URL("../assets/sa-flag.png", import.meta.url).href;

function SaudiFlag() {
  return (
    <img src={saudiFlagUrl} width="24" height="16" alt="Saudi Arabia" className="saudi-flag" />
  );
}

const chartColors = [
  "#509C35",
  "#2d66b3",
  "#df8930",
  "#5558c8",
  "#7c5cb8",
  "#c98a08",
  "#8b95a4",
];

const allocationColumns: ColumnDef[] = [
  { key: "Job Family" },
  { key: "Saudi Labor" },
  { key: "In-House Non-Saudi Labor" },
  { key: "Outsourced Labor" },
  { key: "Total Employees Headcount", label: "Total Headcount" },
  { key: "Total Cost (SAR)" },
];

const targetColumns: ColumnDef[] = [
  { key: "Job Family" },
  { key: "Outsourceability Type" },
  { key: "Driver Value", label: "Driver" },
  { key: "Current Headcount" },
  { key: "Current Ratio" },
  { key: "Minimum Headcount Needed" },
];

const modelColumns: ColumnDef[] = [
  { key: "Job Family" },
  { key: "Outsourceability Type" },
  { key: "Driver Value", label: "Driver" },
  { key: "Current Headcount" },
  { key: "Current In-House Count" },
  { key: "Current Outsourced Count" },
  { key: "Minimum Headcount Needed" },
  { key: "Risk Factor" },
  { key: "Outsourced v1", label: "Outsourced (reference)" },
  { key: "Optimized Outsourced", label: "Outsourced (optimized)" },
  { key: "Optimized In-house Saudi", label: "In-house Saudi (optimized)" },
  { key: "Optimized In-house Non Saudi", label: "In-house non-Saudi (optimized)" },
  { key: "Tenure Driven Minimum" },
];

const auditColumns: ColumnDef[] = [
  { key: "Job Family" },
  { key: "Outsourceability Type" },
  { key: "Current Headcount" },
  { key: "Final Outsourced" },
  { key: "Final In-House" },
  { key: "Minimum Count" },
  { key: "Risk Factor" },
  { key: "Risk-Adjusted Effective Count", label: "Effective Count" },
  { key: "Risk-Adjusted Minimum Met" },
  { key: "Strict In-House Minimum Met" },
  { key: "Saudi Floor Met" },
  { key: "Tenure Floor Met" },
  { key: "Profession Saudization Met" },
];

function TopDrivers({ rows }: { rows: Record<string, unknown>[] }) {
  const topRows = useMemo(() => {
    return [...rows]
      .sort((a, b) => getRowNumber(b, ["Total Cost (SAR)"]) - getRowNumber(a, ["Total Cost (SAR)"]))
      .slice(0, 5);
  }, [rows]);
  const maxCost = Math.max(...topRows.map((row) => getRowNumber(row, ["Total Cost (SAR)"])), 1);

  return (
    <div className="driver-list">
      {topRows.map((row, index) => {
        const cost = getRowNumber(row, ["Total Cost (SAR)"]);
        return (
          <div className="driver-row" key={getString(row, "Job Family") || String(cost)}>
            <div>
              <span className="driver-dot" style={{ background: chartColors[index % chartColors.length] }} />
              <strong>{getString(row, "Job Family")}</strong>
              <span>{formatCompactCurrency(cost)}</span>
            </div>
            <div className="driver-track">
              <div style={{ width: `${Math.max(4, (cost / maxCost) * 100)}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function JobFamilyDrilldowns({ rows }: { rows: Record<string, unknown>[] }) {
  const topRows = useMemo(() => {
    return [...rows]
      .sort((a, b) => getRowNumber(b, ["Total Cost (SAR)"]) - getRowNumber(a, ["Total Cost (SAR)"]))
      .slice(0, 4);
  }, [rows]);

  return (
    <div className="job-family-grid">
      {topRows.map((row) => {
        const family = getString(row, "Job Family");
        const saudi = getRowNumber(row, ["Saudi Labor"]);
        const nonSaudi = getRowNumber(row, ["In-House Non-Saudi Labor"]);
        const outsourced = getRowNumber(row, ["Outsourced Labor"]);
        const totalCost = getRowNumber(row, ["Total Cost (SAR)"]);
        const maxHeadcount = Math.max(saudi, nonSaudi, outsourced, 1);
        return (
          <article className="job-card" key={family || String(totalCost)}>
            <div>
              <h3>{family || "Job family"}</h3>
              <strong>{formatCompactCurrency(totalCost)}</strong>
            </div>
            <div className="mini-bars">
              <span>Saudi</span>
              <div><i style={{ width: `${(saudi / maxHeadcount) * 100}%` }} /></div>
              <b>{formatNumber(saudi, 0)}</b>
              <span>Non-Saudi</span>
              <div><i style={{ width: `${(nonSaudi / maxHeadcount) * 100}%` }} /></div>
              <b>{formatNumber(nonSaudi, 0)}</b>
              <span>Outsourced</span>
              <div><i style={{ width: `${(outsourced / maxHeadcount) * 100}%` }} /></div>
              <b>{formatNumber(outsourced, 0)}</b>
            </div>
          </article>
        );
      })}
    </div>
  );
}

function clientOptimizationStatusLabel(raw: string): string {
  const s = raw.trim();
  if (s === "Matches v4") return "Within prior guardrails";
  return s || "—";
}

function BaselineVsFinalPayroll({
  current,
  optimized,
  savingsAmount,
  savingsPercent,
}: {
  current: number;
  optimized: number;
  savingsAmount: number;
  savingsPercent: number;
}) {
  const max = Math.max(current, optimized, 1);
  const baselinePct = current > 0 ? (current / max) * 100 : 0;
  const optimizedPct = optimized > 0 ? (optimized / max) * 100 : 0;

  return (
    <div className="payroll-compare">
      <div className="payroll-compare-header">
        <p className="eyebrow">Monthly payroll</p>
        <h3>Current baseline vs optimized plan</h3>
      </div>
      <div className="payroll-compare-bars">
        <div className="payroll-compare-row">
          <span className="payroll-compare-label">Current (baseline)</span>
          <div className="payroll-compare-track">
            <div
              className="payroll-compare-fill payroll-compare-fill--baseline"
              style={{ width: `${Math.max(4, baselinePct)}%` }}
            />
          </div>
          <span className="payroll-compare-value">{current ? formatCompactCurrency(current) : "—"}</span>
        </div>
        <div className="payroll-compare-row">
          <span className="payroll-compare-label">Optimized</span>
          <div className="payroll-compare-track">
            <div
              className="payroll-compare-fill payroll-compare-fill--optimized"
              style={{ width: `${Math.max(4, optimizedPct)}%` }}
            />
          </div>
          <span className="payroll-compare-value">{formatCompactCurrency(optimized)}</span>
        </div>
      </div>
      <p className="payroll-compare-summary">
        {current ? (
          <>
            Projected savings <strong>{formatCurrency(savingsAmount)}</strong> per month (
            {formatPercent(savingsPercent)})
          </>
        ) : (
          "Upload a validated baseline to express savings against current payroll."
        )}
      </p>
    </div>
  );
}

function sumRows(rows: Record<string, unknown>[], keys: string[]) {
  return rows.reduce((sum, row) => sum + getRowNumber(row, keys), 0);
}

function OutputKpi({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: "default" | "accent";
}) {
  return (
    <div className={`output-kpi output-kpi--${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function OutputPayrollCard({ current, optimized }: { current: number; optimized: number }) {
  const max = Math.max(current, optimized, 1);
  const currentPct = current > 0 ? (current / max) * 100 : 0;
  const optimizedPct = optimized > 0 ? (optimized / max) * 100 : 0;

  return (
    <div className="output-payroll-card">
      <span>Payroll Before / After</span>
      <div className="output-payroll-rows">
        <div className="output-payroll-row">
          <small>Current Payroll</small>
          <div className="output-payroll-track">
            <i className="output-payroll-fill output-payroll-fill--current" style={{ width: `${Math.max(4, currentPct)}%` }} />
          </div>
          <strong>{current ? formatCurrency(current) : "-"}</strong>
        </div>
        <div className="output-payroll-row">
          <small>Optimized Payroll</small>
          <div className="output-payroll-track">
            <i className="output-payroll-fill output-payroll-fill--optimized" style={{ width: `${Math.max(4, optimizedPct)}%` }} />
          </div>
          <strong>{formatCurrency(optimized)}</strong>
        </div>
      </div>
    </div>
  );
}

function FamilyMixBar({
  label,
  saudi,
  nonSaudi,
  outsourced,
  total,
}: {
  label: string;
  saudi: number;
  nonSaudi: number;
  outsourced: number;
  total: number;
}) {
  const denominator = Math.max(total, saudi + nonSaudi + outsourced, 1);
  const segments = [
    { key: "saudi", label: "Saudi", shortLabel: "Saudi", value: saudi },
    { key: "non-saudi", label: "Non-Saudi", shortLabel: "Non-Saudi", value: nonSaudi },
    { key: "outsourced", label: "Outsourced", shortLabel: "Outs.", value: outsourced },
  ];

  return (
    <span className="family-mix-bar-row">
      <span className="family-mix-bar-label">{label}</span>
      <span className="family-mix-bar" aria-hidden>
        {segments.map((segment) => {
          const pct = segment.value > 0 ? (segment.value / denominator) * 100 : 0;
          const value = formatNumber(segment.value, 0);
          const text = pct >= 18
            ? `${value} ${segment.label}`
            : pct >= 8
              ? `${value} ${segment.shortLabel}`
              : value;

          return (
            <i
              key={segment.key}
              className={`family-mix-bar-segment family-mix-bar-segment--${segment.key}`}
              title={`${label} ${segment.label}: ${value}`}
              style={{ width: `${segment.value > 0 ? Math.max(2, pct) : 0}%` }}
            >
              {segment.value > 0 ? <span>{text}</span> : null}
            </i>
          );
        })}
      </span>
    </span>
  );
}

function FamilyRecommendations({
  results,
  modelRows,
}: {
  results: Record<string, unknown>[];
  modelRows: Record<string, unknown>[];
}) {
  const [openFamilies, setOpenFamilies] = useState<Set<string>>(new Set());
  const modelByFamily = useMemo(() => {
    return new Map(modelRows.map((row) => [getString(row, "Job Family"), row]));
  }, [modelRows]);

  function toggleFamily(family: string) {
    setOpenFamilies((current) => {
      const next = new Set(current);
      if (next.has(family)) next.delete(family);
      else next.add(family);
      return next;
    });
  }

  return (
    <div className="family-recommendations">
      {results.map((row) => {
        const family = getString(row, "Job Family") || "Job family";
        const modelRow = (modelByFamily.get(family) ?? {}) as Record<string, unknown>;
        const isOpen = openFamilies.has(family);
        const currentHeadcount = getRowNumber(modelRow, ["Current Headcount"]);
        const currentSaudi = getRowNumber(modelRow, ["Current Total In-house Saudi", "Total Inhouse Saudi"]);
        const currentNonSaudi = getRowNumber(modelRow, ["Current In-House Non-Saudi Count"]);
        const currentOutsourced = getRowNumber(modelRow, ["Current Outsourced Count"]);
        const optimizedSaudi = getRowNumber(row, ["Saudi Labor"]);
        const optimizedNonSaudi = getRowNumber(row, ["In-House Non-Saudi Labor"]);
        const optimizedOutsourced = getRowNumber(row, ["Outsourced Labor"]);
        const optimizedHeadcount = getRowNumber(row, ["Total Employees Headcount"]);
        const totalCost = getRowNumber(row, ["Total Cost (SAR)"]);
        return (
          <article className={`family-recommendation${isOpen ? " family-recommendation--open" : ""}`} key={family}>
            <button type="button" className="family-recommendation-main" onClick={() => toggleFamily(family)}>
              <span className="family-toggle">{isOpen ? "-" : "+"}</span>
              <strong>{family}</strong>
              <span className="family-mix-bars">
                <FamilyMixBar
                  label="Current"
                  saudi={currentSaudi}
                  nonSaudi={currentNonSaudi}
                  outsourced={currentOutsourced}
                  total={currentHeadcount}
                />
                <FamilyMixBar
                  label="Optimized"
                  saudi={optimizedSaudi}
                  nonSaudi={optimizedNonSaudi}
                  outsourced={optimizedOutsourced}
                  total={optimizedHeadcount}
                />
              </span>
            </button>
            {isOpen ? (
              <div className="family-recommendation-detail">
                <div>
                  <span>Current Saudi</span>
                  <strong>{formatNumber(currentSaudi, 0)}</strong>
                </div>
                <div>
                  <span>Current Non-Saudi</span>
                  <strong>{formatNumber(currentNonSaudi, 0)}</strong>
                </div>
                <div>
                  <span>Current Outsourced</span>
                  <strong>{formatNumber(currentOutsourced, 0)}</strong>
                </div>
                <div>
                  <span>Optimized Saudi</span>
                  <strong>{formatNumber(optimizedSaudi, 0)}</strong>
                </div>
                <div>
                  <span>Optimized Non-Saudi</span>
                  <strong>{formatNumber(optimizedNonSaudi, 0)}</strong>
                </div>
                <div>
                  <span>Optimized Outsourced</span>
                  <strong>{formatNumber(optimizedOutsourced, 0)}</strong>
                </div>
                <div>
                  <span>Total Cost</span>
                  <strong>{formatCurrency(totalCost)}</strong>
                </div>
              </div>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}

type ResultsDashboardProps = {
  optimization: OptimizationResponse;
  targetRows: Record<string, unknown>[];
  detailTab: DetailTab;
  onDetailTabChange: (tab: DetailTab) => void;
  debugEnabled: boolean;
};

export function ResultsDashboard({
  optimization,
  targetRows,
  detailTab,
  onDetailTabChange,
  debugEnabled,
}: ResultsDashboardProps) {
  const summary = optimization.summary;
  const isTargetMode = summary.optimization_mode === "target";
  const currentPayroll = toNumber(summary.current_payroll_cost ?? optimization.metadata.current_payroll_cost);
  const optimizedPayroll = toNumber(summary.optimized_payroll ?? summary.total_cost);
  const savingsAmount = Math.max(0, currentPayroll - optimizedPayroll);
  const rawSavingsFraction = summary.optimized_savings;
  const hasApiSavings =
    typeof rawSavingsFraction === "number" && Number.isFinite(rawSavingsFraction);
  const rawSavingsPercent = toNumber(rawSavingsFraction);
  const savingsPercent = hasApiSavings
    ? rawSavingsPercent <= 1
      ? rawSavingsPercent * 100
      : rawSavingsPercent
    : safeSavingsPercent(currentPayroll, optimizedPayroll);
  const targetHeadcountTotal = toNumber(summary.target_headcount_total);
  const totalCost = toNumber(summary.total_cost);
  const totalSaudi = toNumber(summary.total_saudi_final);
  const totalNonSaudi = toNumber(summary.total_non_saudi_final);
  const totalOutsourced = toNumber(summary.total_outsourced_final);
  const totalEmployees = toNumber(summary.total_employees_final);
  const costSaudi = toNumber(summary.total_cost_saudi);
  const costNonSaudi = toNumber(summary.total_cost_non_saudi);
  const costOutsourced = toNumber(summary.total_cost_outsourced);
  const rawStatus = String(summary.optimization_status || "");
  const statusDisplay = clientOptimizationStatusLabel(rawStatus);
  const statusTone = ["Optimal", "Matches v4"].includes(rawStatus) ? "optimal" : "fallback";
  const currentSaudi = sumRows(optimization.model_processing, ["Current Total In-house Saudi", "Total Inhouse Saudi"]);
  const currentNonSaudi = sumRows(optimization.model_processing, ["Current In-House Non-Saudi Count"]);
  const currentOutsourced = sumRows(optimization.model_processing, ["Current Outsourced Count"]);
  const currentEmployees = currentSaudi + currentNonSaudi + currentOutsourced;

  const hasAuditRows = Boolean(optimization.audit?.length);
  const auditRows = hasAuditRows ? optimization.audit! : optimization.model_processing;

  const perFteSaudi = costSaudi / Math.max(totalSaudi, 1);
  const perFteNonSaudi = costNonSaudi / Math.max(totalNonSaudi, 1);
  const perFteOutsourced = costOutsourced / Math.max(totalOutsourced, 1);

  const compliance = useMemo(() => {
    const rows = auditRows;
    let compliantRows = 0;
    let totalGap = 0;
    rows.forEach((row) => {
      const required = getRowNumber(row, ["Minimum Count", "Minimum Headcount Needed"]);
      const actual = hasAuditRows
        ? getRowNumber(row, ["Risk-Adjusted Effective Count"])
        : getRowNumber(row, ["Optimized In-house Saudi"]) + getRowNumber(row, ["Optimized In-house Non Saudi"]);
      if (actual + 1e-9 >= required) compliantRows += 1;
      else totalGap += required - actual;
    });
    return {
      compliantRows,
      rowCount: rows.length,
      totalGap,
      percent: rows.length ? (compliantRows / rows.length) * 100 : 100,
    };
  }, [auditRows, hasAuditRows]);

  const targetTableRows = useMemo(() => {
    if (targetRows.length) return targetRows;
    return optimization.model_processing.map((row) => ({
      "Job Family": row["Job Family"],
      "Outsourceability Type": row["Outsourceability Type"],
      "Driver Value": row["Driver Value"],
      "Current Headcount": row["Current Headcount"],
      "Current Ratio": row["Current Ratio"],
      "Minimum Headcount Needed": row["Minimum Headcount Needed"],
    }));
  }, [optimization.model_processing, targetRows]);

  const costChartItems = [
    { label: "Saudi labor", value: costSaudi, color: chartColors[0], displayValue: formatCompactCurrency(costSaudi) },
    { label: "In-house non-Saudi", value: costNonSaudi, color: chartColors[1], displayValue: formatCompactCurrency(costNonSaudi) },
    { label: "Outsourced labor", value: costOutsourced, color: chartColors[2], displayValue: formatCompactCurrency(costOutsourced) },
  ];

  const headcountChartItems = [
    { label: "Saudi", value: totalSaudi, color: chartColors[0], displayValue: formatNumber(totalSaudi, 0) },
    { label: "Non-Saudi", value: totalNonSaudi, color: chartColors[1], displayValue: formatNumber(totalNonSaudi, 0) },
    { label: "Outsourced", value: totalOutsourced, color: chartColors[2], displayValue: formatNumber(totalOutsourced, 0) },
  ];

  const currentHeadcountChartItems = [
    { label: "In-house Saudi", value: currentSaudi, color: chartColors[0], displayValue: formatNumber(currentSaudi, 0) },
    { label: "In-house Non-Saudi", value: currentNonSaudi, color: chartColors[1], displayValue: formatNumber(currentNonSaudi, 0) },
    { label: "Outsourced", value: currentOutsourced, color: chartColors[2], displayValue: formatNumber(currentOutsourced, 0) },
  ];

  const optimizedHeadcountChartItems = [
    { label: "In-house Saudi", value: totalSaudi, color: chartColors[0], displayValue: formatNumber(totalSaudi, 0) },
    { label: "In-house Non-Saudi", value: totalNonSaudi, color: chartColors[1], displayValue: formatNumber(totalNonSaudi, 0) },
    { label: "Outsourced", value: totalOutsourced, color: chartColors[2], displayValue: formatNumber(totalOutsourced, 0) },
  ];

  return (
    <section className="results-panel output-panel">
      <div className="output-summary-card">
        <div className="output-summary-head">
          <div>
            <span className="output-eyebrow">Output Summary</span>
            <h2>Manpower Optimization Tool</h2>
          </div>
          <span className={`mode-pill ${isTargetMode ? "mode-pill--target" : "mode-pill--current"}`}>
            {isTargetMode ? "Target Manpower Plan" : "Optimize Current Payroll"}
          </span>
          {statusTone !== "optimal" ? (
            <span className={`status-pill status-pill--${statusTone}`}>{statusDisplay}</span>
          ) : null}
        </div>

        <div className={`output-kpi-grid${isTargetMode ? "" : " output-kpi-grid--payroll"}`}>
          {isTargetMode ? (
            <>
              <OutputKpi label="Target Headcount" value={formatNumber(targetHeadcountTotal || totalEmployees, 0)} tone="accent" />
              <OutputKpi label="Projected Monthly Cost" value={formatCurrency(optimizedPayroll)} />
              <OutputKpi label="Saudization Achieved" value={formatPercent(summary.saudization_achieved)} />
            </>
          ) : (
            <>
              <OutputKpi label="Total Savings Achieved" value={currentPayroll ? formatCurrency(savingsAmount) : "-"} tone="accent" />
              <OutputKpi label="Savings Rate Achieved" value={currentPayroll ? formatPercent(savingsPercent) : "-"} />
              <OutputPayrollCard current={currentPayroll} optimized={optimizedPayroll} />
            </>
          )}
        </div>

        <div className="output-breakdown-grid">
          <DonutChart
            title="Current Manpower Breakdown"
            subtitle="Current"
            centerValue={formatNumber(currentEmployees, 0)}
            centerLabel="Total"
            items={currentHeadcountChartItems}
            tooltipValueFormatter={(value) => formatNumber(value, 0)}
          />
          <div className="output-breakdown-arrow" aria-hidden>→</div>
          <DonutChart
            title="Optimized Manpower Breakdown"
            subtitle="Optimized"
            centerValue={formatNumber(totalEmployees, 0)}
            centerLabel="Total"
            items={optimizedHeadcountChartItems}
            tooltipValueFormatter={(value) => formatNumber(value, 0)}
          />
        </div>
      </div>

      <section className="output-family-section">
        <div className="output-section-head">
          <span className="output-eyebrow">Job Families</span>
          <h3>Recommended Manpower Mix</h3>
        </div>
        <FamilyRecommendations results={optimization.results} modelRows={optimization.model_processing} />
      </section>

      {debugEnabled ? (
        <>
          <div className="detail-tabs detail-tabs--debug" role="tablist" aria-label="Debug result detail tabs">
            <button className={`detail-tab ${detailTab === "insights" ? "active" : ""}`} onClick={() => onDetailTabChange("insights")}>
              Overview
            </button>
            <button className={`detail-tab ${detailTab === "families" ? "active" : ""}`} onClick={() => onDetailTabChange("families")}>
              Job Families
            </button>
            <button className={`detail-tab ${detailTab === "target" ? "active" : ""}`} onClick={() => onDetailTabChange("target")}>
              Target Split
            </button>
            <button className={`detail-tab ${detailTab === "audit" ? "active" : ""}`} onClick={() => onDetailTabChange("audit")}>
              Optimization Audit
            </button>
          </div>

          <div className="detail-panel">
            {detailTab === "insights" ? (
              <div className="insights-panel">
                <div className="insights-summary-row">
                  <BaselineVsFinalPayroll
                    current={currentPayroll}
                    optimized={optimizedPayroll}
                    savingsAmount={savingsAmount}
                    savingsPercent={savingsPercent}
                  />
                  <div className="insights-headcount-donut">
                    <DonutChart
                      title="Headcount mix"
                      subtitle="Optimized allocation"
                      centerValue={formatNumber(totalEmployees, 0)}
                      centerLabel="Employees"
                      items={headcountChartItems}
                      tooltipValueFormatter={(value) => formatNumber(value, 0)}
                    />
                  </div>
                </div>
              </div>
            ) : null}
            {detailTab === "families" ? (
              <DataTable rows={optimization.results} columns={allocationColumns} defaultRows={10} searchable />
            ) : null}
            {detailTab === "target" ? (
              <DataTable rows={targetTableRows} columns={targetColumns} defaultRows={10} compact searchable />
            ) : null}
            {detailTab === "audit" ? (
              <div>
                {compliance.totalGap === 0 && compliance.rowCount > 0 ? (
                  <div className="audit-clean-summary">
                    <div className="audit-clean-summary-head">
                      <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden>
                        <circle cx="10" cy="10" r="9" fill="var(--color-success)" />
                        <path d="M5.5 10.5l3 3 6-6.5" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                      <strong>All {compliance.rowCount} families pass every guardrail</strong>
                    </div>
                  </div>
                ) : null}
                <DataTable rows={auditRows} columns={hasAuditRows ? auditColumns : modelColumns} defaultRows={10} compact searchable />
              </div>
            ) : null}
          </div>
        </>
      ) : null}
    </section>
  );
}
