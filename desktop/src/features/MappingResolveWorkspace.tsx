// Tier 5."Additional Inputs" / Job Families step.
//
// Responsibilities:
//   (1) Resolve unmapped (activity, profession) pairs the workbook surfaced. Until every
//       pair has a resolution, downstream stages stay disabled.
//   (2) Edit existing custom job families that have no payroll rows in the workbook
//       (Target-mode flow). Creating a new custom job family from scratch is currently
//       disabled here.see the deferred "+ Add Job Family" affordance below.
//
// State lives in a parent (App.tsx). On save we call `onApply(updatedFamilies)` which
// re-processes the workbook against the merged mappings server-side.

import { useEffect, useMemo, useState } from "react";

import { SectionHeader } from "../components/SectionHeader";
import type {
  ActivityProfession,
  CustomFamilyCosts,
  CustomFamilySpec,
  OutsourceabilityKind,
  PartialConfig,
  PartialKind,
  UnmappedPair,
  UploadResponse,
} from "../types";

const OUTSOURCEABILITY_OPTIONS: OutsourceabilityKind[] = [
  "Fully Outsourceable",
  "Partially Outsourceable",
  "Not Outsourceable",
];

const PARTIAL_KIND_OPTIONS: { kind: PartialKind; label: string; copy: string }[] = [
  { kind: "percent", label: "Percent", copy: "A given percentage of the family is outsourceable." },
  { kind: "fixed", label: "Fixed in-house count", copy: "A specific number of workers stays in-house; the rest are outsourceable." },
  { kind: "driver", label: "Driver-based", copy: "Outsourcing is capped by a supervisor:worker ratio against another role's headcount." },
];

type Props = {
  uploadInfo: UploadResponse;
  unmappedPairs: UnmappedPair[];
  workbookPairs: ActivityProfession[];
  customFamilies: CustomFamilySpec[];
  // Whether the user has chosen "Input and Optimize a Target Manpower Plan".
  // The "+ Add Job Family" affordance only appears in target mode because a job
  // family with no payroll rows only makes sense when planning toward a future
  // target headcount.
  isTargetMode: boolean;
  busy: boolean;
  onApply: (updated: CustomFamilySpec[]) => void;
  onMapPairsToExisting: (additions: Record<string, string>) => void;
};

type Mode = "view" | "wizard";

type WizardSeed = {
  // Pairs the user has selected to bind to this job family. Empty for a custom job
  // family with no payroll rows.
  pairs: ActivityProfession[];
  // If we are editing an existing custom job family, the index in `customFamilies`.
  editingIndex?: number;
};

export function MappingResolveWorkspace({
  uploadInfo,
  unmappedPairs,
  workbookPairs,
  customFamilies,
  isTargetMode,
  busy,
  onApply,
  onMapPairsToExisting,
}: Props) {
  const [selectedPairs, setSelectedPairs] = useState<Set<string>>(new Set());
  const [mode, setMode] = useState<Mode>("view");
  const [seed, setSeed] = useState<WizardSeed | null>(null);
  const [mapToExistingFamily, setMapToExistingFamily] = useState<string>("");

  function pairKey(p: ActivityProfession) {
    return `${p.activity}|${p.profession}`;
  }

  // Existing canonical families (already in the workbook) the user can route a new
  // profession to without creating a brand-new custom family. Sorted for stable order.
  const existingFamilyNames = useMemo(() => {
    const fromWorkbook = (uploadInfo.families ?? []).map((f) => f.family_name);
    const fromCustom = customFamilies.map((f) => f.family_name);
    return Array.from(new Set([...fromWorkbook, ...fromCustom])).sort();
  }, [uploadInfo.families, customFamilies]);

  function commitMapToExisting() {
    if (!mapToExistingFamily || selectedPairs.size === 0) return;
    const additions: Record<string, string> = {};
    for (const key of selectedPairs) additions[key] = mapToExistingFamily;
    onMapPairsToExisting(additions);
    setSelectedPairs(new Set());
    setMapToExistingFamily("");
  }

  function togglePair(pair: ActivityProfession) {
    const key = pairKey(pair);
    setSelectedPairs((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function startWizardFromSelection() {
    const pairs = unmappedPairs.filter((p) => selectedPairs.has(pairKey(p))).map(({ activity, profession }) => ({ activity, profession }));
    if (pairs.length === 0) return;
    setSeed({ pairs });
    setMode("wizard");
  }

  function startNewJobFamily() {
    setSeed({ pairs: [] });
    setMode("wizard");
  }

  function startEditFamily(idx: number) {
    setSeed({ pairs: customFamilies[idx].source_pairs, editingIndex: idx });
    setMode("wizard");
  }

  function cancelWizard() {
    setSeed(null);
    setMode("view");
  }

  function commitFamilies(newFamilies: CustomFamilySpec[]) {
    let updated = customFamilies.slice();
    if (seed?.editingIndex !== undefined) {
      // Replace the existing entry with the (possibly multiple) updated entries.
      updated.splice(seed.editingIndex, 1, ...newFamilies);
    } else {
      updated = [...updated, ...newFamilies];
    }
    setSeed(null);
    setMode("view");
    setSelectedPairs(new Set());
    onApply(updated);
  }

  function deleteFamily(idx: number) {
    const updated = customFamilies.filter((_, i) => i !== idx);
    onApply(updated);
  }

  return (
    <section className="mapping-workspace">
      <SectionHeader
        eyebrow="Additional Inputs"
        title={`${uploadInfo.job_family_count} Job Families`}
        copy={
          unmappedPairs.length > 0
            ? `${unmappedPairs.length} role${unmappedPairs.length === 1 ? "" : "s"} need input.`
            : undefined
        }
      />

      {mode === "wizard" && seed ? (
        <DefineFamilyWizard
          seed={seed}
          existingFamilies={customFamilies}
          workbookPairs={workbookPairs}
          onCancel={cancelWizard}
          onSave={commitFamilies}
        />
      ) : null}

      {mode === "view" && unmappedPairs.length > 0 ? (
        <div className="card mapping-card">
          <div className="mapping-card-head">
            <strong>Unmapped pairs from {uploadInfo.filename ?? "the workbook"}</strong>
            <span className="mapping-card-hint">Tick the pairs that should map to the same job family, then "Define job family from selected".</span>
          </div>
          <table className="mapping-table">
            <thead>
              <tr>
                <th></th>
                <th>Activity</th>
                <th>Profession</th>
                <th>Rows</th>
              </tr>
            </thead>
            <tbody>
              {unmappedPairs.map((pair) => {
                const key = pairKey(pair);
                return (
                  <tr key={key}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedPairs.has(key)}
                        onChange={() => togglePair(pair)}
                      />
                    </td>
                    <td>{pair.activity}</td>
                    <td>{pair.profession}</td>
                    <td>{pair.count}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div className="mapping-card-actions">
            <button
              className="btn btn-primary"
              disabled={busy || selectedPairs.size === 0}
              onClick={startWizardFromSelection}
            >
              Define job family from selected ({selectedPairs.size})
            </button>
            <div className="mapping-map-to-existing">
              <span className="mapping-map-to-existing-label">or map to existing job family</span>
              <select
                value={mapToExistingFamily}
                onChange={(e) => setMapToExistingFamily(e.target.value)}
                disabled={busy || selectedPairs.size === 0 || existingFamilyNames.length === 0}
                aria-label="Target job family"
              >
                <option value="">Pick a family…</option>
                {existingFamilyNames.map((name) => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
              <button
                className="btn btn-secondary"
                disabled={busy || selectedPairs.size === 0 || !mapToExistingFamily}
                onClick={commitMapToExisting}
              >
                Map ({selectedPairs.size})
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {mode === "view" && customFamilies.length > 0 ? (
        <div className="card mapping-card">
          <div className="mapping-card-head">
            <strong>Custom job families</strong>
          </div>
          <ul className="custom-family-list">
              {customFamilies.map((spec, idx) => (
                <li key={idx} className="custom-family-row">
                  <div className="custom-family-row-head">
                    <strong>{spec.family_name}</strong>
                    <span className="mapping-pill">{spec.outsourceability}</span>
                  </div>
                  <p className="custom-family-row-pairs">
                    {spec.source_pairs.length === 0
                      ? <em>Custom job family (no payroll rows)</em>
                      : spec.source_pairs.map((p) => `${p.activity} – ${p.profession}`).join(" • ")}
                  </p>
                  {spec.partial_config ? (
                    <p className="custom-family-row-meta">
                      Partial config: <code>{summarizePartialConfig(spec.partial_config)}</code>
                    </p>
                  ) : null}
                  {spec.costs ? (
                    <p className="custom-family-row-meta">
                      Costs (Saudi / non-Saudi / outsourced):{" "}
                      <code>{spec.costs.saudi_inhouse} / {spec.costs.non_saudi_inhouse} / {spec.costs.outsourced}</code>
                    </p>
                  ) : null}
                  <div className="custom-family-row-actions">
                    <button className="btn btn-link" disabled={busy} onClick={() => startEditFamily(idx)}>Edit</button>
                    <button className="btn btn-link btn-link-danger" disabled={busy} onClick={() => deleteFamily(idx)}>Delete</button>
                  </div>
                </li>
              ))}
            </ul>
        </div>
      ) : null}

      {mode === "view" && isTargetMode ? (
        <div className="card mapping-card mapping-add-job-family">
          <div className="mapping-card-head">
            <strong>Add a job family for target planning</strong>
            <span className="mapping-card-hint">
              Useful when your Target Manpower Plan needs a job family that does not exist in
              the uploaded workbook yet. Define its costs and outsourceability here, then enter
              its target headcount on the User Assumptions step.
            </span>
          </div>
          <div className="mapping-card-actions">
            <button className="btn btn-secondary" disabled={busy} onClick={startNewJobFamily}>
              + Add Job Family
            </button>
          </div>
        </div>
      ) : null}

    </section>
  );
}

function summarizePartialConfig(config: PartialConfig): string {
  if (config.kind === "percent") return `${Math.round((config.percent ?? 0) * 100)}% outsourceable`;
  if (config.kind === "fixed") return `${config.fixed_count ?? 0} fixed in-house`;
  return `Driver: ${config.driver_activity ?? "?"} – ${config.driver_profession ?? "?"} (${config.max_ratio ?? "1:?"})`;
}

// ---------------------------------------------------------------------------
// Define-Family wizard

type WizardProps = {
  seed: WizardSeed;
  existingFamilies: CustomFamilySpec[];
  workbookPairs: ActivityProfession[];
  onCancel: () => void;
  onSave: (newFamilies: CustomFamilySpec[]) => void;
};

function DefineFamilyWizard({
  seed,
  existingFamilies,
  workbookPairs,
  onCancel,
  onSave,
}: WizardProps) {
  const editing = seed.editingIndex !== undefined;
  const baseFamily = editing ? existingFamilies[seed.editingIndex!] : undefined;
  const isBrandNew = seed.pairs.length === 0;

  const [familyName, setFamilyName] = useState(baseFamily?.family_name ?? "");
  // For multi-pair seeds, decide whether to fold into one family or split per activity.
  const [groupingMode, setGroupingMode] = useState<"single" | "split">("single");
  const [outsourceability, setOutsourceability] = useState<OutsourceabilityKind>(
    baseFamily?.outsourceability ?? "Partially Outsourceable",
  );
  const [partialKind, setPartialKind] = useState<PartialKind>(
    baseFamily?.partial_config?.kind ?? "percent",
  );
  const [percent, setPercent] = useState<number>(baseFamily?.partial_config?.percent ?? 0.5);
  const [fixedCount, setFixedCount] = useState<number>(baseFamily?.partial_config?.fixed_count ?? 0);
  const [driverActivity, setDriverActivity] = useState<string>(baseFamily?.partial_config?.driver_activity ?? "");
  const [driverProfession, setDriverProfession] = useState<string>(baseFamily?.partial_config?.driver_profession ?? "");
  const [driverRatioN, setDriverRatioN] = useState<number>(() => {
    const ratio = baseFamily?.partial_config?.max_ratio;
    if (!ratio) return 10;
    const parts = ratio.split(":");
    const n = Number(parts[1]);
    return Number.isFinite(n) && n > 0 ? n : 10;
  });
  const [costs, setCosts] = useState<CustomFamilyCosts>(
    baseFamily?.costs ?? { saudi_inhouse: 0, non_saudi_inhouse: 0, outsourced: 0 },
  );

  const distinctActivities = useMemo(
    () => Array.from(new Set(workbookPairs.map((p) => p.activity))).sort(),
    [workbookPairs],
  );
  const professionsForActivity = useMemo(() => {
    if (!driverActivity) return [] as string[];
    return Array.from(
      new Set(workbookPairs.filter((p) => p.activity === driverActivity).map((p) => p.profession)),
    ).sort();
  }, [workbookPairs, driverActivity]);

  // If the user has multi-pair seed and chooses split, family name becomes a prefix.
  useEffect(() => {
    if (seed.pairs.length <= 1) setGroupingMode("single");
  }, [seed.pairs.length]);

  function buildPartialConfig(): PartialConfig | null {
    if (outsourceability !== "Partially Outsourceable") return null;
    if (partialKind === "percent") return { kind: "percent", percent };
    if (partialKind === "fixed") return { kind: "fixed", fixed_count: fixedCount };
    return {
      kind: "driver",
      driver_activity: driverActivity,
      driver_profession: driverProfession,
      max_ratio: `1:${driverRatioN}`,
    };
  }

  function buildSavePayload(): CustomFamilySpec[] {
    const partialCfg = buildPartialConfig();
    const includeCosts = isBrandNew;
    const baseSpec = (name: string, pairs: ActivityProfession[]): CustomFamilySpec => ({
      family_name: name,
      outsourceability,
      source_pairs: pairs,
      partial_config: partialCfg ?? null,
      costs: includeCosts ? { ...costs } : null,
    });

    if (groupingMode === "split" && seed.pairs.length > 1) {
      const prefix = familyName.trim() || "Custom";
      // One family per pair, suffixed by activity + profession.
      return seed.pairs.map((p) => baseSpec(`${prefix} (${p.activity} – ${p.profession})`, [p]));
    }
    return [baseSpec(familyName.trim() || (isBrandNew ? "New Job Family" : `Custom (${seed.pairs.length} pairs)`), seed.pairs)];
  }

  const canSave =
    familyName.trim().length > 0 &&
    (outsourceability !== "Partially Outsourceable" ||
      (partialKind === "percent" && percent >= 0 && percent <= 1) ||
      (partialKind === "fixed" && fixedCount >= 0) ||
      (partialKind === "driver" && driverActivity && driverProfession && driverRatioN > 0)) &&
    (!isBrandNew ||
      (costs.saudi_inhouse > 0 && costs.non_saudi_inhouse > 0 && costs.outsourced > 0));

  return (
    <div className="card mapping-card wizard-card">
      <div className="mapping-card-head">
        <strong>{editing ? "Edit job family" : isBrandNew ? "Add a job family" : `Define job family from ${seed.pairs.length} pair${seed.pairs.length === 1 ? "" : "s"}`}</strong>
      </div>

      {seed.pairs.length > 0 ? (
        <div className="wizard-pairs">
          {seed.pairs.map((p) => (
            <span key={`${p.activity}|${p.profession}`} className="mapping-pill">{p.activity} – {p.profession}</span>
          ))}
        </div>
      ) : null}

      {seed.pairs.length > 1 ? (
        <fieldset className="wizard-field">
          <legend>Is this the same role across activities?</legend>
          <label className="wizard-radio">
            <input type="radio" checked={groupingMode === "single"} onChange={() => setGroupingMode("single")} />
            Yes, fold all selected pairs into one job family
          </label>
          <label className="wizard-radio">
            <input type="radio" checked={groupingMode === "split"} onChange={() => setGroupingMode("split")} />
            No, create a separate job family for each pair (the name becomes a prefix)
          </label>
        </fieldset>
      ) : null}

      <fieldset className="wizard-field">
        <legend>{groupingMode === "split" ? "Name of job family (prefix)" : "Name of job family"}</legend>
        <input
          type="text"
          className="wizard-text-input"
          value={familyName}
          placeholder={isBrandNew ? "e.g. Drone Pilot" : "e.g. Logistics Driver"}
          onChange={(e) => setFamilyName(e.target.value)}
        />
      </fieldset>

      <fieldset className="wizard-field">
        <legend>Outsourceability</legend>
        {OUTSOURCEABILITY_OPTIONS.map((option) => (
          <label key={option} className="wizard-radio">
            <input type="radio" checked={outsourceability === option} onChange={() => setOutsourceability(option)} />
            {option}
          </label>
        ))}
      </fieldset>

      {outsourceability === "Partially Outsourceable" ? (
        <fieldset className="wizard-field wizard-field--reveal">
          <legend>How is the outsourceable share decided?</legend>
          {PARTIAL_KIND_OPTIONS.map(({ kind, label, copy }) => (
            <label key={kind} className="wizard-radio">
              <input type="radio" checked={partialKind === kind} onChange={() => setPartialKind(kind)} />
              <span className="wizard-radio-text">
                <strong>{label}</strong>
                <span className="wizard-radio-copy">{copy}</span>
              </span>
            </label>
          ))}

          {partialKind === "percent" ? (
            <label className="wizard-inline-input">
              <span>Outsourceable share (%)</span>
              <input
                type="number"
                min={0}
                max={100}
                step={5}
                value={Math.round(percent * 100)}
                onFocus={(e) => e.currentTarget.select()}
                onChange={(e) => setPercent(Math.max(0, Math.min(100, Number(e.target.value))) / 100)}
              />
            </label>
          ) : null}

          {partialKind === "fixed" ? (
            <label className="wizard-inline-input">
              <span>Minimum in-house headcount</span>
              <input
                type="number"
                min={0}
                step={1}
                value={fixedCount}
                onFocus={(e) => e.currentTarget.select()}
                onChange={(e) => setFixedCount(Math.max(0, Number(e.target.value) | 0))}
              />
            </label>
          ) : null}

          {partialKind === "driver" ? (
            <div className="wizard-driver-grid">
              <label className="wizard-inline-input">
                <span>Driver activity</span>
                <select value={driverActivity} onChange={(e) => setDriverActivity(e.target.value)}>
                  <option value="" disabled>Pick an activity…</option>
                  {distinctActivities.map((a) => <option key={a} value={a}>{a}</option>)}
                </select>
              </label>
              <label className="wizard-inline-input">
                <span>Driver profession</span>
                <select value={driverProfession} onChange={(e) => setDriverProfession(e.target.value)} disabled={!driverActivity}>
                  <option value="" disabled>Pick a profession…</option>
                  {professionsForActivity.map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </label>
              <label className="wizard-inline-input">
                <span>Max ratio (1 : N)</span>
                <input
                  type="number"
                  min={1}
                  step={1}
                  value={driverRatioN}
                  onFocus={(e) => e.currentTarget.select()}
                  onChange={(e) => setDriverRatioN(Math.max(1, Number(e.target.value) | 0))}
                />
              </label>
            </div>
          ) : null}
        </fieldset>
      ) : null}

      {isBrandNew ? (
        <fieldset className="wizard-field">
          <legend>Unit costs (required for custom job families)</legend>
          <p className="wizard-radio-copy">
            The job family has no payroll rows in the workbook, so the optimizer needs explicit per-employee costs.
          </p>
          <label className="wizard-inline-input">
            <span>Saudi in-house unit cost</span>
            <input
              type="number" min={0} step={50}
              value={costs.saudi_inhouse}
              onFocus={(e) => e.currentTarget.select()}
              onChange={(e) => setCosts({ ...costs, saudi_inhouse: Math.max(0, Number(e.target.value) || 0) })}
            />
          </label>
          <label className="wizard-inline-input">
            <span>Non-Saudi in-house unit cost</span>
            <input
              type="number" min={0} step={50}
              value={costs.non_saudi_inhouse}
              onFocus={(e) => e.currentTarget.select()}
              onChange={(e) => setCosts({ ...costs, non_saudi_inhouse: Math.max(0, Number(e.target.value) || 0) })}
            />
          </label>
          <label className="wizard-inline-input">
            <span>Outsourced unit cost</span>
            <input
              type="number" min={0} step={50}
              value={costs.outsourced}
              onFocus={(e) => e.currentTarget.select()}
              onChange={(e) => setCosts({ ...costs, outsourced: Math.max(0, Number(e.target.value) || 0) })}
            />
          </label>
        </fieldset>
      ) : null}

      <div className="mapping-card-actions">
        <button className="btn btn-secondary" onClick={onCancel}>Cancel</button>
        <button
          className="btn btn-primary"
          disabled={!canSave}
          onClick={() => onSave(buildSavePayload())}
        >
          {editing ? "Save changes" : "Save family"}
        </button>
      </div>
    </div>
  );
}
