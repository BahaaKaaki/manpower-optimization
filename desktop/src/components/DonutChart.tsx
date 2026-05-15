import { useState } from "react";

import type { ChartItem } from "../types";

function formatExactCurrency(value: number): string {
  if (value >= 1_000_000) return `SAR ${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `SAR ${(value / 1_000).toFixed(1)}K`;
  return `SAR ${value.toLocaleString()}`;
}

function createConicGradient(items: ChartItem[], hoveredIndex: number | null) {
  const total = items.reduce((sum, item) => sum + item.value, 0);
  if (!total) return "conic-gradient(rgba(240,242,247,1) 0 360deg)";

  let cursor = 0;
  const segments = items.map((item, i) => {
    const start = cursor;
    const end = cursor + (item.value / total) * 360;
    cursor = end;
    const color = hoveredIndex !== null && hoveredIndex !== i
      ? `color-mix(in srgb, ${item.color} 40%, transparent)`
      : item.color;
    return `${color} ${start}deg ${end}deg`;
  });
  return `conic-gradient(${segments.join(", ")})`;
}

type DonutChartProps = {
  title: string;
  subtitle: string;
  centerValue: string;
  centerLabel?: string;
  items: ChartItem[];
  tooltipValueFormatter?: (value: number) => string;
};

export function DonutChart({ title, subtitle, centerValue, centerLabel, items, tooltipValueFormatter }: DonutChartProps) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const total = items.reduce((sum, item) => sum + item.value, 0);

  const hoveredItem = hoveredIndex !== null ? items[hoveredIndex] : null;
  const hoveredPct = hoveredItem && total ? ((hoveredItem.value / total) * 100).toFixed(1) : null;
  let labelCursor = 0;

  return (
    <article className="donut-card" onMouseLeave={() => setHoveredIndex(null)}>
      <div className="chart-copy">
        <p className="eyebrow">{subtitle}</p>
        <h3>{title}</h3>
      </div>
      <div className="donut-layout">
        <div
          className="donut"
          style={{ background: createConicGradient(items, hoveredIndex) }}
          aria-label={`${title}: ${items.map((item) => `${item.label} ${item.displayValue}`).join(", ")}`}
        >
          {items.map((item, index) => {
            const pct = total ? (item.value / total) * 100 : 0;
            const start = labelCursor;
            labelCursor += pct;
            if (!item.value || pct < 2) return null;

            const angle = (start + pct / 2) * 3.6 - 90;
            const radians = (angle * Math.PI) / 180;
            const radius = pct > 14 ? 34 : pct < 6 ? (index % 2 === 0 ? 41 : 31) : 37;
            const isHovered = hoveredIndex === index;
            const label = pct > 14
              ? `${item.displayValue} ${pct.toFixed(1)}%`
              : `${pct.toFixed(1)}%`;

            return (
              <span
                key={item.label}
                className={`donut-slice-label${isHovered ? " active" : ""}`}
                style={{
                  left: `${50 + Math.cos(radians) * radius}%`,
                  top: `${50 + Math.sin(radians) * radius}%`,
                }}
              >
                {label}
              </span>
            );
          })}
          <div>
            <strong>{hoveredItem ? hoveredPct + "%" : centerValue}</strong>
            <span>{hoveredItem ? hoveredItem.label : (centerLabel || "Total")}</span>
          </div>
        </div>
        <div className="chart-legend">
          {items.map((item, index) => {
            const isHovered = hoveredIndex === index;
            return (
              <div
                key={item.label}
                className={`chart-legend-row${hoveredIndex !== null && !isHovered ? " dimmed" : ""}${isHovered ? " hovered" : ""}`}
                onMouseEnter={() => setHoveredIndex(index)}
              >
                <span style={{ background: item.color }} />
                <p>{item.label}</p>
              </div>
            );
          })}
        </div>
        {hoveredItem && (
          <div className="chart-tooltip">
            <span className="chart-tooltip-dot" style={{ background: hoveredItem.color }} />
            <div>
              <strong>{hoveredItem.label}</strong>
              <span>{tooltipValueFormatter ? tooltipValueFormatter(hoveredItem.value) : formatExactCurrency(hoveredItem.value)}</span>
              <span>{hoveredPct}%</span>
            </div>
          </div>
        )}
      </div>
    </article>
  );
}
