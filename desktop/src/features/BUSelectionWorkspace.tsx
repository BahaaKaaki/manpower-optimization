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
  // Tile click: set this BU as active and advance to Data Upload.
  onUse: (code: BusinessUnitCode) => void;
  // Edit icon click: open the BU Configuration panel for review/editing.
  onConfigure: (code: BusinessUnitCode) => void;
};

export function BUSelectionWorkspace({ activeBU, onUse, onConfigure }: Props) {
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
        <img className="bu-selection-hero-mark" src={cpcHolding} alt="CPC Holding" />
        <h1>Choose a Business Unit</h1>
      </header>

      <div className="bu-grid" role="list">
        {BUSINESS_UNITS.map((bu, idx) => {
          const isSelected = activeBU === bu.code;
          const shortName = bu.code.replace(/_/g, " ");
          // hasCustomConfig is intentionally not surfaced — that's a Configure-panel concern.
          customConfiguredBUs.has(bu.code);
          return (
            <article
              key={bu.code}
              role="listitem"
              className={`bu-tile${isSelected ? " bu-tile--selected" : ""}`}
              style={{ animationDelay: `${idx * 50}ms` } as React.CSSProperties}
            >
              <button
                type="button"
                className="bu-tile-body"
                onClick={() => onUse(bu.code)}
                aria-pressed={isSelected}
                aria-label={isSelected ? `Continue with ${bu.name}` : `Use ${bu.name}`}
              >
                {bu.logoSrc ? (
                  <img src={bu.logoSrc} alt={bu.name} />
                ) : (
                  <span className="bu-tile-placeholder">{shortName}</span>
                )}
              </button>
              <div className="bu-tile-foot">
                <button
                  type="button"
                  className="bu-tile-foot-configure"
                  onClick={() => onConfigure(bu.code)}
                  aria-label={`Configure ${bu.name}`}
                >
                  Configure
                </button>
                <span
                  className={`bu-tile-foot-use${isSelected ? " bu-tile-foot-use--active" : ""}`}
                  aria-hidden
                >
                  {isSelected ? (
                    <>
                      <span className="bu-tile-foot-use-glyph">✓</span>
                      Active
                    </>
                  ) : (
                    <>
                      Use
                      <span className="bu-tile-foot-use-glyph">→</span>
                    </>
                  )}
                </span>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
