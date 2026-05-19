import { useEffect, useState } from "react";

import type { BusinessUnit, BusinessUnitCode } from "../types";
import { persistGet } from "../utils/persistence";

import cpcHolding from "../assets/bu-logos/cpc-holding.png";

// `active` here is the *seeded* state. MGIC ships configured by default. At runtime
// any BU with a saved `bu:<code>:configuration` in local persistence is also treated
// as configured (see configuredBUs state below).
//
// Logos are intentionally OMITTED for now — every BU renders a typographic placeholder
// until proper brand assets are dropped into `desktop/src/assets/bu-logos/` with the
// expected filenames (mgic.png, uaac.png, fast.png, sacodeco.png, sphinx-glass.png,
// premco-precast.png, premco-ready-mix.png, bahra-steel.png, ucc.png). Add the import
// and the `logoSrc` field below to wire any new asset in.
export const BUSINESS_UNITS: BusinessUnit[] = [
  { code: "MGIC", name: "Marble & Granite International Company", active: true },
  { code: "UAAC", name: "United Arab Aluminium Company", active: false },
  { code: "FAST", name: "FAST Waterproofing", active: false },
  { code: "SACODECO", name: "SACODECO Woodwork", active: false },
  { code: "SPHINX", name: "Sphinx Glass", active: false },
  { code: "PREMCO_PRECAST", name: "Premco Precast", active: false },
  { code: "PREMCO_READY_MIX", name: "Premco Ready Mix", active: false },
  { code: "BAHRA_STEEL", name: "Bahra Steel", active: false },
  { code: "UCC", name: "UCC", active: false },
];

type Props = {
  activeBU: BusinessUnitCode | null;
  onOpen: (code: BusinessUnitCode) => void;
};

export function BUSelectionWorkspace({ activeBU, onOpen }: Props) {
  // A BU has a "custom" configuration when the user uploaded an Excel override file
  // for it. Otherwise the BU runs on the tool's defaults.which is a perfectly valid
  // state (so we never block selection on it).
  const [customConfiguredBUs, setCustomConfiguredBUs] = useState<Set<BusinessUnitCode>>(new Set());

  useEffect(() => {
    let cancelled = false;
    void Promise.all(
      BUSINESS_UNITS.map(async (bu) => {
        const saved = await persistGet<unknown>(`bu:${bu.code}:configuration`, null);
        return { code: bu.code, hasOverrides: saved !== null };
      }),
    ).then((rows) => {
      if (cancelled) return;
      setCustomConfiguredBUs(new Set(rows.filter((r) => r.hasOverrides).map((r) => r.code)));
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="bu-selection">
      <header className="bu-selection-hero">
        <div className="bu-selection-hero-mark">
          <img src={cpcHolding} alt="CPC Holding" />
        </div>
        <div className="bu-selection-hero-text">
          <span className="bu-selection-hero-eyebrow">CPC Holding Group</span>
          <h1>Choose your Business Unit</h1>
          <p>
            Each BU has its own configuration. Click a card to review the setup,
            customize via Excel, and start optimizing.
          </p>
        </div>
      </header>

      <div className="bu-grid" role="list">
        {BUSINESS_UNITS.map((bu, idx) => {
          const isSelected = activeBU === bu.code;
          const hasCustomConfig = customConfiguredBUs.has(bu.code);
          const shortName = bu.code.replace(/_/g, " ");
          return (
            <button
              key={bu.code}
              role="listitem"
              type="button"
              className={`bu-card${hasCustomConfig ? " bu-card--custom" : " bu-card--defaults"}${
                isSelected ? " bu-card--selected" : ""
              }`}
              onClick={() => onOpen(bu.code)}
              aria-pressed={isSelected}
              style={{ animationDelay: `${idx * 60}ms` } as React.CSSProperties}
            >
              {/* Accent bar at the very top that grows on hover */}
              <span className="bu-card-rail" aria-hidden />

              <div className="bu-card-status" aria-hidden>
                <span className={`bu-card-status-dot bu-card-status-dot--${hasCustomConfig ? "custom" : "defaults"}`} />
                {hasCustomConfig ? "Custom configuration" : "Using tool defaults"}
              </div>

              <div className="bu-card-logo">
                {bu.logoSrc ? (
                  <img src={bu.logoSrc} alt={`${bu.name} logo`} />
                ) : (
                  <span className="bu-card-logo-placeholder-code">{shortName}</span>
                )}
              </div>

              <div className="bu-card-body">
                <span className="bu-card-code">{shortName}</span>
                <span className="bu-card-name">{bu.name}</span>
              </div>

              <div className="bu-card-footer">
                <span className="bu-card-cta">
                  {hasCustomConfig ? "Review configuration" : "Open and configure"}
                </span>
                <span className="bu-card-arrow" aria-hidden>
                  <svg viewBox="0 0 16 16" fill="none">
                    <path
                      d="M3 8h10m0 0L9 4m4 4l-4 4"
                      stroke="currentColor"
                      strokeWidth="1.6"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
