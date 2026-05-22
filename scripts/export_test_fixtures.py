"""Export the workbook fixtures used by the test suite so the consultant can
inspect the exact Excel shapes the tool expects.

Produces three files in docs/fixtures/:

  1. sample_payroll_with_performance.xlsx
       Payroll with the new (Phase 3) 'Manpower Performance' column on the
       Inhouse sheet. Same column layout the high-performer tests build.
  2. sample_payroll_without_performance.xlsx
       Identical shape WITHOUT the column — demonstrates the auto-default
       (every row → 3.0) behavior.
  3. sample_bu_configuration_MGIC.xlsx
       MGIC's full BU configuration workbook (7 sheets) using the tool's
       hardcoded MGIC mappings. This is what the BU Configuration panel
       downloads in the desktop app.

Run from the repo root:
    .venv/Scripts/python.exe scripts/export_test_fixtures.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from openpyxl import Workbook

from manpower_app.bu_config_io import BUConfigurationPayload, build_workbook
from manpower_app.mappings import (
    ACTIVITY_MAPPING,
    JOB_FAMILY_MAPPING,
    PROFESSION_MAPPING,
)


OUT_DIR = ROOT / "docs" / "fixtures"


INHOUSE_HEADERS_WITH_PERF = [
    "No", "Location", "Profession", "Nationality",
    "Total Paid", "Total Unpaid",
    "Basic", "Housing Paid", "Trans Paid", "Medical Paid", "EOS Paid", "Value O.T (SAR)",
    "Manpower Performance",
]
INHOUSE_HEADERS_NO_PERF = INHOUSE_HEADERS_WITH_PERF[:-1]

SUB_HEADERS = [
    "No", "Working in", "Profession", "Nationality", "Basic",
    "Housing Paid", "Trans Paid", "Food", "Gosi", "Value O.T (SAR)",
    "Government Fees", "E.O.S monthly", "Service Margin",
]


# (Location, Profession, Nationality, perf_score)
# Realistic small sample spanning three job families with mixed nationalities
# and a spread of performance scores so the consultant can see the column in
# action across the 1-5 range.
SAMPLE_PAYROLL_ROWS: list[tuple[str, str, str, int]] = [
    # Skilled Labor — 6 employees, 2 high performers (>= 4)
    ("Quarries", "Skilled Labor", "non-saudi", 5),
    ("Quarries", "Skilled Labor", "non-saudi", 4),
    ("Quarries", "Skilled Labor", "non-saudi", 3),
    ("Quarries", "Skilled Labor", "non-saudi", 2),
    ("Quarries", "Skilled Labor", "non-saudi", 3),
    ("Quarries", "Skilled Labor", "Saudi",     5),
    # Heavy Equipment Operator — 4 employees, 1 high performer
    ("Quarries", "Heavy Equipment Operator", "non-saudi", 4),
    ("Quarries", "Heavy Equipment Operator", "non-saudi", 3),
    ("Quarries", "Heavy Equipment Operator", "non-saudi", 2),
    ("Quarries", "Heavy Equipment Operator", "Saudi",     3),
    # Quarries Foreman (supervisor) — 2 employees, both high performers
    ("Quarries", "Quarries Foreman", "Saudi",     5),
    ("Quarries", "Quarries Foreman", "non-saudi", 4),
]


def _build_payroll(with_performance: bool) -> Workbook:
    wb = Workbook()
    inh = wb.active
    inh.title = "Inhouse"
    inh.append(INHOUSE_HEADERS_WITH_PERF if with_performance else INHOUSE_HEADERS_NO_PERF)
    for idx, (loc, prof, nat, score) in enumerate(SAMPLE_PAYROLL_ROWS):
        # 5000 paid + 4000 basic + allowances, no OT.
        row = [100 + idx, loc, prof, nat, 5000, 0, 4000, 500, 200, 200, 100, 0]
        if with_performance:
            row.append(score)
        inh.append(row)

    sub = wb.create_sheet("Subcontractor")
    sub.append(SUB_HEADERS)
    # One subcontractor row per (location, profession) pair so the optimizer
    # has outsourced cost data for every in-house family.
    seen: set[tuple[str, str]] = set()
    for loc, prof, _nat, _s in SAMPLE_PAYROLL_ROWS:
        key = (loc, prof)
        if key in seen:
            continue
        seen.add(key)
        sub.append([
            200 + len(seen), loc, prof, "non-saudi",
            1500, 100, 50, 30, 0, 0, 0, 0, 80,
        ])
    return wb


def _save(wb: Workbook, name: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    wb.save(path)
    return path


def _build_mgic_bu_config_workbook() -> bytes:
    """MGIC is the seeded BU. Build its config workbook (7 sheets) so the
    consultant has a complete reference of the BU-config format."""
    config = BUConfigurationPayload(
        profession_mapping=dict(PROFESSION_MAPPING),
        activity_mapping=dict(ACTIVITY_MAPPING),
        job_family_mapping=dict(JOB_FAMILY_MAPPING),
    )
    return build_workbook("MGIC", "Modern Gulf Industries Company", config)


def main() -> None:
    p1 = _save(_build_payroll(with_performance=True),
               "sample_payroll_with_performance.xlsx")
    p2 = _save(_build_payroll(with_performance=False),
               "sample_payroll_without_performance.xlsx")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bu_path = OUT_DIR / "sample_bu_configuration_MGIC.xlsx"
    bu_path.write_bytes(_build_mgic_bu_config_workbook())

    print(f"Wrote {p1}")
    print(f"Wrote {p2}")
    print(f"Wrote {bu_path}")


if __name__ == "__main__":
    main()
