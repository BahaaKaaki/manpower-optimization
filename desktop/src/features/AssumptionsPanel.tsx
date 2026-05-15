import { useEffect, useState } from "react";

import { fetchAssumptions } from "../api/client";
import { SectionHeader } from "../components/SectionHeader";
import type { AssumptionsCatalog } from "../types";

export function AssumptionsPanel() {
  const [catalog, setCatalog] = useState<AssumptionsCatalog | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchAssumptions()
      .then((data) => {
        if (!cancelled) setCatalog(data);
      })
      .catch((caught: unknown) => {
        if (!cancelled) setError(caught instanceof Error ? caught.message : String(caught));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <details className="card assumptions-panel" open={open} onToggle={(event) => setOpen(event.currentTarget.open)}>
        <summary>
          <SectionHeader
            eyebrow="Debug"
            title="Assumptions & Rules"
            copy={`Could not load: ${error}`}
          />
        </summary>
      </details>
    );
  }

  if (!catalog) return null;

  return (
    <details className="card assumptions-panel" open={open} onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary>
        <SectionHeader
          eyebrow="Debug"
          title="Assumptions & Rules"
        />
      </summary>

      <div className="assumptions-body">
        <Section title="Outsourceability rules">
          <p className="assumption-description">{catalog.outsourceability_rules.description}</p>
          <KVList
            entries={Object.entries(catalog.outsourceability_rules.categories)}
            keyHeader="Category"
            valueHeader="Meaning"
          />
          <h4>Per job family</h4>
          <KVList
            entries={Object.entries(catalog.outsourceability_rules.rules_by_family)}
            keyHeader="Job family"
            valueHeader="Classification"
            compact
          />
        </Section>

        <Section title="Special profession rules">
          {catalog.special_profession_rules.map((rule, idx) => (
            <div key={idx} className="assumption-row">
              <div className="assumption-row-head">
                <strong>{rule.rule}</strong>
                <span className="assumption-row-tag">{rule.families.join(", ")}</span>
              </div>
              <p>{rule.description}</p>
            </div>
          ))}
        </Section>

        <Section title="Maximum supervisor:worker ratios">
          <p className="assumption-description">{catalog.maximum_ratio_rules.description}</p>
          <KVList
            entries={Object.entries(catalog.maximum_ratio_rules.rules_by_family)}
            keyHeader="Job family"
            valueHeader="Ratio"
            compact
          />
        </Section>

        <Section title="Default optimization settings">
          {catalog.default_optimization_settings.map((entry) => (
            <div key={entry.key} className="assumption-row">
              <div className="assumption-row-head">
                <strong>{entry.key}</strong>
                <span className="assumption-row-tag">
                  {String(entry.default)} ({entry.unit})
                </span>
              </div>
              <p>{entry.description}</p>
            </div>
          ))}
        </Section>

        <Section title="Cost assumptions">
          {catalog.cost_assumptions.map((entry, idx) => (
            <div key={idx} className="assumption-row">
              <div className="assumption-row-head">
                <strong>{entry.name}</strong>
                <span className="assumption-row-tag">{entry.value}</span>
              </div>
              <p>{entry.description}</p>
            </div>
          ))}
        </Section>

        <Section title="Risk formula">
          <p className="assumption-row-tag">{catalog.risk_formula.formula}</p>
          <p>{catalog.risk_formula.description}</p>
          <p>
            <em>Risk = 0:</em> {catalog.risk_formula.edge_case_risk_zero}
          </p>
        </Section>

        <Section title="Input format expected">
          <p>
            <strong>Required sheets:</strong> {catalog.input_format.required_sheets.join(", ")}
          </p>
          <p>
            <strong>Required Inhouse columns:</strong> {catalog.input_format.required_inhouse_columns.join(", ")}
          </p>
          <p>
            <strong>Required Subcontractor columns:</strong>{" "}
            {catalog.input_format.required_subcontractor_columns.join(", ")}
          </p>
          <p>
            <strong>Saudi nationality:</strong> {catalog.input_format.nationality_detection}
          </p>
          <p>
            <strong>Tenure detection:</strong> {catalog.input_format.tenure_detection}
          </p>
        </Section>
      </div>
    </details>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="assumptions-section">
      <h3>{title}</h3>
      {children}
    </section>
  );
}

function KVList({
  entries,
  keyHeader,
  valueHeader,
  compact = false,
}: {
  entries: Array<[string, string]>;
  keyHeader: string;
  valueHeader: string;
  compact?: boolean;
}) {
  return (
    <table className={compact ? "assumptions-kv-table assumptions-kv-table-compact" : "assumptions-kv-table"}>
      <thead>
        <tr>
          <th>{keyHeader}</th>
          <th>{valueHeader}</th>
        </tr>
      </thead>
      <tbody>
        {entries.map(([key, value]) => (
          <tr key={key}>
            <td>{key}</td>
            <td>{value}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
