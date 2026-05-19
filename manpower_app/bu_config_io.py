"""
Excel template export/import for per-BU Configuration (batch-2 150526 enhancements).

Round trip:
    config_json -> build_workbook(...) -> .xlsx bytes -> parse_workbook(...) -> config_json

The workbook is intentionally human-readable. Single ``Value`` column per row — what the
user puts there is what the optimizer uses for this BU. There is no separate "default"
or "override" column: an empty Value means the row is not configured for this BU.

For an unconfigured BU, the starter file lists every canonical family/supervisor name
in column A with blank Value columns — the user fills the values that apply to their
operations (or deletes rows that don't). For a configured BU, the downloaded file is
the saved configuration verbatim.

The valid outsourceability values and the canonical ratio/driver shapes mirror
``manpower_app/rules.py`` and ``manpower_api/app.py:assumption_defaults``.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

from manpower_app.rules import MAXIMUM_RATIO_RULES, OUTSOURCEABILITY_RULES


VALID_OUTSOURCEABILITY = {"Fully Outsourceable", "Partially Outsourceable", "Not Outsourceable"}
RATIO_PATTERN = re.compile(r"^\s*1\s*:\s*\d+\s*$")

# Canonical supervisor families that have drivers. Used to list rows in the starter
# Drivers sheet so the user knows which supervisors accept driver definitions.
DRIVER_SUPERVISORS = sorted([
    "Quarries Foreman",
    "Production Foreman",
    "Installation Foreman",
    "Showroom Supervisor",
    "Safety Officer",
    "Quarries Supervisor",
    "Installation Supervisor",
    "Factory Supervisor",
])

ENGINE_KNOBS = [
    ("Saudi cost premium", "Multiplier applied to non-Saudi in-house cost (must be ≥ 1.0, ≤ 3.0)."),
    ("Outsource cost discount", "Fraction outsourcing is cheaper than non-Saudi in-house (0.0–1.0). Leave blank to use workbook value."),
]


@dataclass
class BUConfigurationPayload:
    """Plain-old container matching the desktop ``BUConfiguration`` type."""
    outsourceability_overrides: dict[str, str] = field(default_factory=dict)
    ratio_overrides: dict[str, str] = field(default_factory=dict)
    driver_overrides: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    saudi_cost_premium: float | None = None
    outsource_cost_discount: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "outsourceability_overrides": dict(self.outsourceability_overrides),
            "ratio_overrides": dict(self.ratio_overrides),
            "driver_overrides": {k: list(v) for k, v in self.driver_overrides.items()},
            "saudi_cost_premium": self.saudi_cost_premium,
            "outsource_cost_discount": self.outsource_cost_discount,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "BUConfigurationPayload":
        payload = payload or {}
        return cls(
            outsourceability_overrides=dict(payload.get("outsourceability_overrides") or {}),
            ratio_overrides=dict(payload.get("ratio_overrides") or {}),
            driver_overrides={
                k: list(v) for k, v in (payload.get("driver_overrides") or {}).items()
            },
            saudi_cost_premium=payload.get("saudi_cost_premium"),
            outsource_cost_discount=payload.get("outsource_cost_discount"),
        )

    def is_empty(self) -> bool:
        return (
            not self.outsourceability_overrides
            and not self.ratio_overrides
            and not self.driver_overrides
            and self.saudi_cost_premium is None
            and self.outsource_cost_discount is None
        )


def build_workbook(
    bu_code: str,
    bu_name: str | None,
    config: BUConfigurationPayload,
) -> bytes:
    """Return XLSX bytes that the user can edit and re-upload.

    When ``config`` is empty (a fresh BU), the workbook is a "starter": canonical
    family/supervisor names are listed in column A so the user knows what's available,
    but the Value column is blank for them to fill. When ``config`` is populated, the
    rows shown ARE the saved configuration — Values are pre-filled.

    Note: Saudi pay premium and outsource cost discount are NOT in this workbook —
    those are scenario knobs the user adjusts on the User Assumptions step, not
    BU-level constraints."""
    wb = openpyxl.Workbook()
    _build_readme_sheet(wb.active, bu_code, bu_name, config.is_empty())
    _build_outsourceability_sheet(wb.create_sheet("Outsourceability"), config)
    _build_ratios_sheet(wb.create_sheet("Ratios"), config)
    _build_drivers_sheet(wb.create_sheet("Drivers"), config)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def parse_workbook(source: bytes | io.BytesIO) -> tuple[BUConfigurationPayload, list[str]]:
    """Return (config, errors). When ``errors`` is non-empty the caller should NOT save.

    Reads the ``Value`` column of each sheet. Blank Value cells mean the row is not
    configured for this BU and will not appear in the saved payload."""
    if isinstance(source, bytes):
        source = io.BytesIO(source)
    try:
        wb = openpyxl.load_workbook(source, data_only=True)
    except Exception as exc:
        return BUConfigurationPayload(), [f"Could not open workbook: {exc}"]

    errors: list[str] = []
    config = BUConfigurationPayload()
    required_sheets = {"Outsourceability", "Ratios", "Drivers"}
    missing = sorted(required_sheets - set(wb.sheetnames))
    if missing:
        return config, [f"Missing sheet(s): {', '.join(missing)}. Use the downloaded template."]

    _parse_outsourceability(wb["Outsourceability"], config, errors)
    _parse_ratios(wb["Ratios"], config, errors)
    _parse_drivers(wb["Drivers"], config, errors)
    # Engine Knobs sheet was removed from the BU workbook — Saudi pay premium and
    # outsource cost discount are now scenario-only knobs on User Assumptions. We
    # still parse the old sheet if it's present, so legacy workbooks keep working.
    if "Engine Knobs" in wb.sheetnames:
        _parse_engine_knobs(wb["Engine Knobs"], config, errors)
    return config, errors


# ──────────────────────────────────────────────────────────────────────────
# Helpers — building each sheet


_HEADER_FILL = PatternFill(start_color="336B24", end_color="336B24", fill_type="solid")
_HEADER_FONT = Font(bold=True, color="FFFFFF")
_INSTRUCTION_FONT = Font(italic=True, color="475264")


def _style_header_row(ws, row=1):
    for cell in ws[row]:
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = Alignment(vertical="center", horizontal="left")


def _build_readme_sheet(ws, bu_code: str, bu_name: str | None, is_empty: bool):
    ws.title = "README"
    ws["A1"] = "Business Unit"
    ws["B1"] = bu_code
    ws["A2"] = "Display name"
    ws["B2"] = bu_name or ""
    if is_empty:
        instructions = (
            "Starter file for a fresh BU. The four configuration sheets list the canonical "
            "names (Job Family, Supervisor Family, Engine Knob) in column A. Fill the Value "
            "column for the rows that apply to this BU — delete rows that don't apply or "
            "leave their Value blank. For the Drivers sheet, add one row per Activity + "
            "Profession pair you want counted for each supervisor family. Save and upload."
        )
    else:
        instructions = (
            "Current saved configuration for this BU. Edit any Value to change it; clear a "
            "Value to remove that row from the configuration. For Drivers, add or remove "
            "rows under each supervisor family. Save the file and upload it back."
        )
    ws["A4"] = instructions
    ws["A4"].alignment = Alignment(wrap_text=True, vertical="top")
    ws["A4"].font = _INSTRUCTION_FONT
    ws.merge_cells("A4:E10")
    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 40


def _build_outsourceability_sheet(ws, config: BUConfigurationPayload):
    ws.append(["Job Family", "Value"])
    _style_header_row(ws)
    # If the user has saved values, list THOSE families. Otherwise list the full canonical
    # family set as a reference with blank Values (the starter case).
    if config.outsourceability_overrides:
        rows = sorted(config.outsourceability_overrides.items())
        for family, value in rows:
            ws.append([family, value])
    else:
        for family in sorted(OUTSOURCEABILITY_RULES.keys()):
            ws.append([family, ""])
    ws.column_dimensions["A"].width = 32
    ws.column_dimensions["B"].width = 28
    # Reference list of valid values (column D-E so it doesn't clash with the data columns).
    ws["D1"] = "Valid values"
    ws["D1"].font = _INSTRUCTION_FONT
    for i, value in enumerate(sorted(VALID_OUTSOURCEABILITY), start=2):
        cell = ws.cell(row=i, column=4, value=value)
        cell.font = _INSTRUCTION_FONT
    ws.column_dimensions["D"].width = 26


def _build_ratios_sheet(ws, config: BUConfigurationPayload):
    ws.append(["Supervisor Family", "Value (e.g. 1:10)"])
    _style_header_row(ws)
    if config.ratio_overrides:
        rows = sorted(config.ratio_overrides.items())
        for family, value in rows:
            ws.append([family, value])
    else:
        for family in sorted(MAXIMUM_RATIO_RULES.keys()):
            ws.append([family, ""])
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 22


def _build_drivers_sheet(ws, config: BUConfigurationPayload):
    ws.append(["Supervisor Family", "Activity", "Profession"])
    _style_header_row(ws)
    if config.driver_overrides:
        for family in sorted(config.driver_overrides.keys()):
            for entry in config.driver_overrides[family]:
                ws.append([
                    family,
                    entry.get("activity", ""),
                    entry.get("profession", ""),
                ])
    else:
        # Starter: list the supervisor family names so the user knows which ones accept
        # drivers. Activity + Profession are blank for the user to fill.
        for family in DRIVER_SUPERVISORS:
            ws.append([family, "", ""])
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 22
    ws.column_dimensions["C"].width = 22
    ws["E1"] = "Add one row per Activity + Profession pair you want counted as a driver"
    ws["E1"].font = _INSTRUCTION_FONT
    ws.column_dimensions["E"].width = 60


def _build_engine_knobs_sheet(ws, config: BUConfigurationPayload):
    ws.append(["Knob", "Value", "Notes"])
    _style_header_row(ws)
    value_lookup = {
        "Saudi cost premium": config.saudi_cost_premium,
        "Outsource cost discount": config.outsource_cost_discount,
    }
    for key, note in ENGINE_KNOBS:
        value = value_lookup[key]
        ws.append([key, "" if value is None else value, note])
    for row in ws.iter_rows(min_row=2):
        row[2].font = _INSTRUCTION_FONT
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 14
    ws.column_dimensions["C"].width = 80


# ──────────────────────────────────────────────────────────────────────────
# Helpers — parsing each sheet


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_outsourceability(ws, config: BUConfigurationPayload, errors: list[str]):
    for row in ws.iter_rows(min_row=2, values_only=True):
        family = _cell_text(row[0] if len(row) > 0 else "")
        value = _cell_text(row[1] if len(row) > 1 else "")
        if not family:
            continue
        if not value:
            # Blank Value = not configured for this BU. Skip silently.
            continue
        if family not in OUTSOURCEABILITY_RULES:
            errors.append(f"Outsourceability: unknown job family '{family}' (typo?)")
            continue
        if value not in VALID_OUTSOURCEABILITY:
            errors.append(
                f"Outsourceability: '{family}' value must be one of {sorted(VALID_OUTSOURCEABILITY)}, got '{value}'"
            )
            continue
        config.outsourceability_overrides[family] = value


def _parse_ratios(ws, config: BUConfigurationPayload, errors: list[str]):
    for row in ws.iter_rows(min_row=2, values_only=True):
        family = _cell_text(row[0] if len(row) > 0 else "")
        value = _cell_text(row[1] if len(row) > 1 else "")
        if not family:
            continue
        if not value:
            continue
        if family not in MAXIMUM_RATIO_RULES:
            errors.append(f"Ratios: unknown supervisor family '{family}' (typo?)")
            continue
        if not RATIO_PATTERN.match(value):
            errors.append(
                f"Ratios: '{family}' value must be of the form '1:N' (got '{value}')"
            )
            continue
        config.ratio_overrides[family] = value.replace(" ", "")


def _parse_drivers(ws, config: BUConfigurationPayload, errors: list[str]):
    """Drivers: every non-blank (Activity OR Profession) row under a Supervisor Family
    is a driver entry. Multiple rows per family are aggregated into a single list."""
    valid_supervisors = set(DRIVER_SUPERVISORS)
    for row in ws.iter_rows(min_row=2, values_only=True):
        family = _cell_text(row[0] if len(row) > 0 else "")
        activity = _cell_text(row[1] if len(row) > 1 else "")
        profession = _cell_text(row[2] if len(row) > 2 else "")
        if not family:
            continue
        if family not in valid_supervisors:
            errors.append(f"Drivers: unknown supervisor family '{family}' (typo?)")
            continue
        if not activity and not profession:
            # The user listed the supervisor name (starter row) but didn't fill it in.
            # Skip — they haven't configured this supervisor's drivers yet.
            continue
        config.driver_overrides.setdefault(family, []).append({
            "activity": activity,
            "profession": profession,
        })


def _parse_engine_knobs(ws, config: BUConfigurationPayload, errors: list[str]):
    for row in ws.iter_rows(min_row=2, values_only=True):
        key = _cell_text(row[0] if len(row) > 0 else "")
        value_raw = row[1] if len(row) > 1 else None
        if not key:
            continue
        if isinstance(value_raw, str) and not value_raw.strip():
            value_raw = None
        if value_raw is None:
            continue
        try:
            value = float(value_raw)
        except (TypeError, ValueError):
            errors.append(f"Engine knobs: '{key}' value must be a number (got '{value_raw}')")
            continue
        if key == "Saudi cost premium":
            if value < 1.0 or value > 3.0:
                errors.append(f"Engine knobs: 'Saudi cost premium' must be between 1.0 and 3.0 (got {value})")
                continue
            config.saudi_cost_premium = value
        elif key == "Outsource cost discount":
            if value < 0.0 or value > 1.0:
                errors.append(f"Engine knobs: 'Outsource cost discount' must be between 0 and 1 (got {value})")
                continue
            config.outsource_cost_discount = value
        else:
            errors.append(f"Engine knobs: unknown knob '{key}' (typo?)")
