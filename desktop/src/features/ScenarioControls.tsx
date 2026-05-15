import { type ReactNode, useState } from "react";

import { SectionHeader } from "../components/SectionHeader";
import type { FamilySummary, Settings } from "../types";

function ToggleSwitch({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="toggle-switch">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="toggle-switch-input"
      />
      <span className="toggle-switch-track">
        <span className="toggle-switch-thumb" />
      </span>
    </label>
  );
}

function FieldStack({ children }: { children: ReactNode }) {
  return <div className="control-fields scenario-accordion-fields">{children}</div>;
}

function ToggleField({
  label,
  checked,
  onChange,
  hint,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
  hint?: string;
}) {
  return (
    <div className="control-row control-row--toggle">
      <div>
        <span className="control-row-label">{label}</span>
        {hint ? <span className="control-row-hint">{hint}</span> : null}
      </div>
      <ToggleSwitch checked={checked} onChange={onChange} />
    </div>
  );
}

function NumberField({
  label,
  value,
  onChange,
  min,
  max,
  step = 0.01,
  disabled = false,
  suffix,
  hint,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  disabled?: boolean;
  suffix?: string;
  hint?: string;
}) {
  const isRatio = max === 1 && (min ?? 0) >= 0;

  return (
    <div className={`control-row control-row--number ${disabled ? "control-row--disabled" : ""}`}>
      <div className="control-row-info">
        <span className="control-row-label">{label}</span>
        {hint ? <span className="control-row-hint">{hint}</span> : null}
        <span className="control-row-value">
          {isRatio ? `${(value * 100).toFixed(0)}%` : value}
          {suffix && !isRatio ? ` ${suffix}` : ""}
        </span>
      </div>
      {isRatio ? (
        <input
          type="range"
          className="control-slider"
          min={min}
          max={max}
          step={step}
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(Number(e.target.value))}
        />
      ) : (
        <div className="number-input-wrap">
          <input
            type="number"
            className="number-input"
            min={min}
            max={max}
            step={step}
            value={value}
            disabled={disabled}
            onFocus={(e) => e.currentTarget.select()}
            onChange={(e) => {
              const raw = e.target.value;
              onChange(raw === "" ? 0 : Number(raw));
            }}
          />
          {suffix ? <span className="number-input-suffix">{suffix}</span> : null}
        </div>
      )}
    </div>
  );
}

type AccordionId = "saudization" | "cost" | "protection" | "custom" | "target";

const MAX_RATIO_DEFAULTS: Array<{ family: string; defaultRatio: string }> = [
  { family: "Quarries Foreman", defaultRatio: "1:15" },
  { family: "Safety Officer", defaultRatio: "1:50" },
  { family: "Quarries Supervisor", defaultRatio: "1:10" },
  { family: "Installation Supervisor", defaultRatio: "1:12" },
  { family: "Production Foreman", defaultRatio: "1:15" },
  { family: "Factory Supervisor", defaultRatio: "1:10" },
  { family: "Installation Foreman", defaultRatio: "1:40" },
  { family: "Showroom Supervisor", defaultRatio: "1:10" },
];

function parseRatioDenominator(ratio: string): number {
  const parts = ratio.split(":");
  if (parts.length !== 2) return 0;
  const denom = Number(parts[1]);
  return Number.isFinite(denom) && denom > 0 ? denom : 0;
}

function AccordionSection({
  id,
  title,
  subtitle,
  isOpen,
  onToggle,
  children,
}: {
  id: AccordionId;
  title: string;
  subtitle?: string;
  isOpen: boolean;
  onToggle: (id: AccordionId) => void;
  children: ReactNode;
}) {
  return (
    <div className={`scenario-accordion${isOpen ? " scenario-accordion--open" : ""}`}>
      <button
        type="button"
        className="scenario-accordion-trigger"
        aria-expanded={isOpen}
        aria-controls={`scenario-panel-${id}`}
        id={`scenario-trigger-${id}`}
        onClick={() => onToggle(id)}
      >
        <span className="scenario-accordion-trigger-text">
          <strong>{title}</strong>
          {subtitle ? <span className="scenario-accordion-sub">{subtitle}</span> : null}
        </span>
        <span className="scenario-accordion-chevron" aria-hidden>
          {isOpen ? "−" : "+"}
        </span>
      </button>
      <div
        className="scenario-accordion-panel"
        id={`scenario-panel-${id}`}
        role="region"
        aria-labelledby={`scenario-trigger-${id}`}
        hidden={!isOpen}
      >
        {children}
      </div>
    </div>
  );
}

type ScenarioControlsProps = {
  settings: Settings;
  onUpdate: <K extends keyof Settings>(key: K, value: Settings[K]) => void;
  families?: FamilySummary[];
};

export function ScenarioControls({ settings, onUpdate, families = [] }: ScenarioControlsProps) {
  const [openSections, setOpenSections] = useState<Set<AccordionId>>(() => new Set(["saudization"]));

  function toggleSection(id: AccordionId) {
    setOpenSections((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const isTargetMode = settings.optimization_mode === "target";
  const allFamilyNames = Array.from(
    new Set([
      ...families.map((f) => f.family_name),
      ...settings.custom_families.map((f) => f.family_name),
    ]),
  ).sort();
  const familyCurrentLookup = new Map(families.map((f) => [f.family_name, f.current_headcount]));

  function setTargetHeadcount(family: string, value: number | null) {
    const next = { ...settings.target_headcounts };
    if (value === null) {
      delete next[family];
    } else {
      next[family] = Math.max(0, value | 0);
    }
    onUpdate("target_headcounts", next);
  }

  function setMode(mode: Settings["optimization_mode"]) {
    onUpdate("optimization_mode", mode);
    setOpenSections((current) => {
      const next = new Set(current);
      if (mode === "target") next.add("target");
      else next.delete("target");
      return next;
    });
  }

  return (
    <>
      <section className="mode-panel">
        <SectionHeader title="Optimization Mode" />

        <div
          className={`mode-toggle-card${isTargetMode ? " mode-toggle-card--target" : " mode-toggle-card--current"}`}
          role="radiogroup"
          aria-label="Optimization mode"
        >
          <div className="mode-toggle-segmented">
            <button
              type="button"
              className={`mode-toggle-option${!isTargetMode ? " mode-toggle-option--active" : ""}`}
              role="radio"
              aria-checked={!isTargetMode}
              onClick={() => setMode("current")}
            >
              <span className="mode-toggle-option-label">Optimize Current Payroll</span>
            </button>
            <button
              type="button"
              className={`mode-toggle-option${isTargetMode ? " mode-toggle-option--active" : ""}`}
              role="radio"
              aria-checked={isTargetMode}
              onClick={() => setMode("target")}
            >
              <span className="mode-toggle-option-label">Target Manpower Plan</span>
            </button>
          </div>
        </div>
      </section>

      <section className="controls-panel">
        <SectionHeader title="Inputs" />

        <div className="scenario-accordion-stack">
          <AccordionSection
            id="saudization"
            title="Saudization & Risk"
            isOpen={openSections.has("saudization")}
            onToggle={toggleSection}
          >
            <FieldStack>
              <ToggleField
                label="Enforce overall Saudization"
                checked={settings.enforce_saudization}
                onChange={(value) => onUpdate("enforce_saudization", value)}
              />
              <NumberField
                label="Overall rate"
                min={0}
                max={1}
                value={settings.saudization_rate}
                onChange={(value) => onUpdate("saudization_rate", value)}
              />
              <NumberField
                label="Engineers"
                min={0}
                max={1}
                value={settings.engineer_saudization_rate}
                onChange={(value) => onUpdate("engineer_saudization_rate", value)}
              />
              <NumberField
                label="Sales"
                min={0}
                max={1}
                value={settings.sales_saudization_rate}
                onChange={(value) => onUpdate("sales_saudization_rate", value)}
              />
              <NumberField
                label="Management"
                min={0}
                max={1}
                value={settings.management_saudization_rate}
                onChange={(value) => onUpdate("management_saudization_rate", value)}
              />
              <hr className="control-divider" />
              <NumberField
                label="Risk factor"
                hint="Outsourced workers count as (1 − risk) of an in-house worker for the minimum-headcount constraint. At 0 the haircut is disabled."
                min={0}
                max={1}
                value={settings.risk_factor}
                onChange={(value) => onUpdate("risk_factor", value)}
              />
              <ToggleField
                label="Use negotiated rates"
                checked={settings.negotiated_rates}
                onChange={(value) => onUpdate("negotiated_rates", value)}
              />
              <NumberField
                label="Insurance cost"
                value={settings.negotiated_insurance_cost}
                disabled={!settings.negotiated_rates}
                suffix="SAR"
                onChange={(value) => onUpdate("negotiated_insurance_cost", value)}
              />
              <NumberField
                label="Service margin"
                value={settings.negotiated_service_margin}
                disabled={!settings.negotiated_rates}
                suffix="SAR"
                onChange={(value) => onUpdate("negotiated_service_margin", value)}
              />
            </FieldStack>
          </AccordionSection>

          <AccordionSection
            id="protection"
            title="Workforce Protection"
            isOpen={openSections.has("protection")}
            onToggle={toggleSection}
          >
            <FieldStack>
              <ToggleField
                label="Allow reducing Saudi headcount"
                hint="Off by default to protect current Saudi employees."
                checked={settings.can_reduce_current_saudi}
                onChange={(value) => onUpdate("can_reduce_current_saudi", value)}
              />
              <ToggleField
                label="Protect tenured employees"
                checked={settings.protect_tenured_inhouse}
                onChange={(value) => onUpdate("protect_tenured_inhouse", value)}
              />
              <NumberField
                label="Minimum tenure"
                min={0}
                max={60}
                step={0.5}
                value={settings.tenure_threshold_years}
                disabled={!settings.protect_tenured_inhouse}
                suffix="years"
                onChange={(value) => onUpdate("tenure_threshold_years", value)}
              />
            </FieldStack>
          </AccordionSection>

          {isTargetMode ? (
          <AccordionSection
            id="target"
            title="Target Manpower Plan"
            isOpen={openSections.has("target")}
            onToggle={toggleSection}
          >
            <FieldStack>
              <p className="control-row-hint">
                Type target headcount per family.
              </p>
              {allFamilyNames.length === 0 ? (
                <p className="mapping-empty">No families yet — upload a workbook first.</p>
              ) : (
                <table className="target-headcount-table">
                  <thead>
                    <tr>
                      <th>Family</th>
                      <th>Current</th>
                      <th>Target</th>
                    </tr>
                  </thead>
                  <tbody>
                    {allFamilyNames.map((family) => {
                      const currentHc = familyCurrentLookup.get(family);
                      const targetHc = settings.target_headcounts[family];
                      const placeholder = currentHc !== undefined ? String(currentHc) : "0";
                      return (
                        <tr key={family}>
                          <td>{family}</td>
                          <td>{currentHc !== undefined ? currentHc : <em>new</em>}</td>
                          <td>
                            <input
                              type="number"
                              min={0}
                              step={1}
                              className="number-input target-headcount-input"
                              value={targetHc !== undefined ? targetHc : ""}
                              placeholder={placeholder}
                              onFocus={(e) => e.currentTarget.select()}
                              onChange={(e) => {
                                const v = e.target.value;
                                if (v === "") setTargetHeadcount(family, null);
                                else setTargetHeadcount(family, Number(v));
                              }}
                            />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </FieldStack>
          </AccordionSection>
          ) : null}
        </div>

        <div className="advanced-settings-block">
          <AccordionSection
            id="custom"
            title="Advanced Settings"
            isOpen={openSections.has("custom")}
            onToggle={toggleSection}
          >
            <FieldStack>
              <NumberField
                label="Saudi cost premium"
                hint="Saudi in-house cost as a multiple of non-Saudi in-house cost. Floored at 1.0× so Saudis cannot be cheaper than non-Saudis. Default 1.10 = 10% more expensive."
                min={1}
                max={3}
                step={0.05}
                value={settings.saudi_cost_premium}
                suffix="× non-Saudi"
                onChange={(value) => onUpdate("saudi_cost_premium", value)}
              />
              <ToggleField
                label="Override outsource cost"
                hint="When on, outsource cost is set as a fraction of non-Saudi in-house cost (replaces workbook value)."
                checked={settings.outsource_cost_discount !== null}
                onChange={(value) =>
                  onUpdate("outsource_cost_discount", value ? 0.2 : (null as unknown as number))
                }
              />
              <NumberField
                label="Outsource discount vs non-Saudi"
                min={0}
                max={1}
                step={0.05}
                value={settings.outsource_cost_discount ?? 0}
                disabled={settings.outsource_cost_discount === null}
                onChange={(value) => onUpdate("outsource_cost_discount", value)}
              />
              <RatioOverrideEditor
                overrides={settings.max_ratio_overrides}
                onUpdate={(next) => onUpdate("max_ratio_overrides", next)}
              />
            </FieldStack>
          </AccordionSection>
        </div>
      </section>
    </>
  );
}

function RatioOverrideEditor({
  overrides,
  onUpdate,
}: {
  overrides: Record<string, string>;
  onUpdate: (next: Record<string, string>) => void;
}) {
  return (
    <div className="ratio-overrides">
      <div className="ratio-overrides-head">
        <span className="control-row-label">Max supervisor:worker ratios</span>
        <span className="control-row-hint">
          One supervisor / foreman per N workers. Leave at default unless the policy has been
          revised. Editing one row only changes that family.
        </span>
      </div>
      <div className="ratio-overrides-grid">
        {MAX_RATIO_DEFAULTS.map(({ family, defaultRatio }) => {
          const overrideRatio = overrides[family];
          const effective = overrideRatio ?? defaultRatio;
          const denom = parseRatioDenominator(effective);
          return (
            <label key={family} className="ratio-override-row">
              <span className="ratio-override-family">{family}</span>
              <span className="ratio-override-control">
                <span className="ratio-override-prefix">1 :</span>
                <input
                  type="number"
                  min={1}
                  step={1}
                  className="number-input ratio-override-input"
                  value={denom || ""}
                  placeholder={parseRatioDenominator(defaultRatio).toString()}
                  onFocus={(event) => event.currentTarget.select()}
                  onChange={(event) => {
                    const next = { ...overrides };
                    const value = Number(event.target.value);
                    if (!Number.isFinite(value) || value <= 0) {
                      delete next[family];
                    } else {
                      next[family] = `1:${value}`;
                    }
                    onUpdate(next);
                  }}
                />
                {overrideRatio ? (
                  <button
                    type="button"
                    className="ratio-override-reset"
                    onClick={() => {
                      const next = { ...overrides };
                      delete next[family];
                      onUpdate(next);
                    }}
                  >
                    Reset
                  </button>
                ) : (
                  <span className="ratio-override-default">default</span>
                )}
              </span>
            </label>
          );
        })}
      </div>
    </div>
  );
}
