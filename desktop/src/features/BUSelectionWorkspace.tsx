import { useEffect, useState } from "react";

import type { BusinessUnit, BusinessUnitCode } from "../types";
import { persistGet } from "../utils/persistence";

import cpcHolding from "../assets/bu-logos/cpc-holding.png";
import mgicLogo from "../assets/bu-logos/mgic.png";
import uaacLogo from "../assets/bu-logos/uaac.png";
import fastLogo from "../assets/bu-logos/fast.png";
import sacodecoLogo from "../assets/bu-logos/sacodeco.png";
import sphinxLogo from "../assets/bu-logos/sphinx-glass.png";
import premcoPrecastLogo from "../assets/bu-logos/premco-precast.png";
import premcoReadyMixLogo from "../assets/bu-logos/premco-ready-mix.png";
import bahraSteelLogo from "../assets/bu-logos/bahra-steel.png";
import uccLogo from "../assets/bu-logos/ucc.png";

// `active` here is the *seeded* state. MGIC ships configured by default. At runtime
// any BU with a saved `bu:<code>:configuration` in local persistence is also treated
// as configured (see configuredBUs state below).
export const BUSINESS_UNITS: BusinessUnit[] = [
  { code: "MGIC", name: "Marble & Granite International Company", logoSrc: mgicLogo, active: true },
  { code: "UAAC", name: "United Arab Aluminium Company", logoSrc: uaacLogo, active: false },
  { code: "FAST", name: "FAST Waterproofing", logoSrc: fastLogo, active: false },
  { code: "SACODECO", name: "SACODECO Woodwork", logoSrc: sacodecoLogo, active: false },
  { code: "SPHINX", name: "Sphinx Glass", logoSrc: sphinxLogo, active: false },
  { code: "PREMCO_PRECAST", name: "Premco Precast", logoSrc: premcoPrecastLogo, active: false },
  { code: "PREMCO_READY_MIX", name: "Premco Ready Mix", logoSrc: premcoReadyMixLogo, active: false },
  { code: "BAHRA_STEEL", name: "Bahra Steel", logoSrc: bahraSteelLogo, active: false },
  { code: "UCC", name: "UCC Steel Structures", logoSrc: uccLogo, active: false },
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
