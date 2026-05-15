"""Single source of truth for hardcoded business rules and assumptions baked into the tool.

This module exists so that anyone reviewing the tool can see — without reading code —
every rule, default value, and built-in assumption the optimization model relies on.
Anything that needs to change is meant to be flagged and discussed.

The :func:`build_assumptions_catalog` function returns a JSON-serializable structure
that the API exposes via ``GET /assumptions`` and the desktop UI renders.

When you add or change a hardcoded rule somewhere in the codebase, **also update this
file**. If a rule lives only in ``rules.py`` / ``mappings.py`` / ``costs.py`` and is not
referenced here, reviewers won't know it exists.
"""

from __future__ import annotations

from typing import Any

from manpower_app.rules import (
    HQ_FIXED_INHOUSE_FAMILIES,
    MAXIMUM_RATIO_RULES,
    OUTSOURCEABILITY_RULES,
)


def build_assumptions_catalog() -> dict[str, Any]:
    """Return a structured catalog of every hardcoded rule and default in the tool.

    Sections:

    * ``outsourceability_rules`` — per-job-family classification (Fully / Partially / Not).
    * ``special_profession_rules`` — non-default per-profession behaviors that override the
      generic LP (Clerk/Controller HQ-fixed, etc.).
    * ``maximum_ratio_rules`` — supervisor:worker ratios used to derive minimum-headcount.
    * ``default_optimization_settings`` — defaults applied to ``OptimizationSettings`` if
      the user does not override them in the UI.
    * ``cost_assumptions`` — magic numbers in the cost model (overtime rate, Saudi
      premium, service-fee cap, fallback multipliers).
    * ``input_format`` — required workbook structure and how the tool detects nationality
      and tenure.
    * ``risk_formula`` — the risk-adjusted minimum-headcount formula.
    """
    return {
        "outsourceability_rules": _outsourceability_section(),
        "special_profession_rules": _special_profession_section(),
        "maximum_ratio_rules": _maximum_ratio_section(),
        "default_optimization_settings": _default_settings_section(),
        "cost_assumptions": _cost_assumptions_section(),
        "input_format": _input_format_section(),
        "risk_formula": _risk_formula_section(),
    }


def _outsourceability_section() -> dict[str, Any]:
    return {
        "description": (
            "Each job family is classified as one of three outsourceability categories. "
            "This determines the upper bound on how many of those workers the optimizer "
            "is allowed to outsource. Job families not listed here default to "
            "'Partially Outsourceable'."
        ),
        "categories": {
            "Fully Outsourceable": "All workers in this family can be outsourced (no in-house floor from this rule).",
            "Partially Outsourceable": "Outsourcing is capped by the family's max-ratio rule (driver-based) or a special rule (HQ-fixed).",
            "Not Outsourceable": "All workers in this family must be in-house — the optimizer cannot outsource any of them.",
        },
        "rules_by_family": dict(sorted(OUTSOURCEABILITY_RULES.items())),
    }


def _special_profession_section() -> list[dict[str, Any]]:
    return [
        {
            "families": sorted(HQ_FIXED_INHOUSE_FAMILIES),
            "rule": "HQ-fixed in-house",
            "description": (
                "The current Head Office headcount for these families stays in-house; "
                "the rest of the family's workers are eligible for outsourcing. If the "
                "planned total drops below the current HQ count, all workers stay in-house."
            ),
            "applies_to_categories": ["Partially Outsourceable"],
            "implemented_in": "manpower_app/optimization.py:_max_outsourced_allowed",
        },
        {
            "families": ["Engineer", "Administration", "Management", "Executive Management"],
            "rule": "All in-house",
            "description": (
                "These professional families are not outsourced — they remain fully in-house. "
                "Listed here for visibility — the underlying mechanism is the "
                "'Not Outsourceable' classification in the outsourceability rules above."
            ),
            "applies_to_categories": ["Not Outsourceable"],
            "implemented_in": "manpower_app/rules.py:OUTSOURCEABILITY_RULES",
        },
    ]


def _maximum_ratio_section() -> dict[str, Any]:
    return {
        "description": (
            "Supervisor:worker ratios drive the minimum-headcount-needed calculation for "
            "supervisor / foreman families. For example, '1:15' means one Quarries Foreman "
            "is needed for every 15 Quarries laborers. Families not listed here have no "
            "ratio-based minimum and rely on driver counts instead. These defaults can be "
            "overridden per-run via the 'Custom assumptions' section in the scenario controls."
        ),
        "user_overridable": True,
        "rules_by_family": dict(sorted(MAXIMUM_RATIO_RULES.items())),
    }


def _default_settings_section() -> list[dict[str, Any]]:
    return [
        {
            "key": "saudization_rate",
            "default": 0.30,
            "unit": "ratio",
            "description": "Minimum share of in-house workforce that must be Saudi nationals when 'enforce_saudization' is on.",
        },
        {
            "key": "risk_factor",
            "default": 0.25,
            "unit": "ratio",
            "description": (
                "Outsourced worker discount in the risk-adjusted minimum-headcount constraint. "
                "An outsourced worker contributes (1 - risk_factor) of an in-house worker "
                "for the purpose of meeting the minimum-headcount-needed floor."
            ),
        },
        {
            "key": "engineer_saudization_rate",
            "default": 0.25,
            "unit": "ratio",
            "description": "Minimum Saudi share of in-house Engineers (Vision 2030 alignment).",
        },
        {
            "key": "sales_saudization_rate",
            "default": 0.60,
            "unit": "ratio",
            "description": "Minimum Saudi share of in-house Sales / Representative roles.",
        },
        {
            "key": "management_saudization_rate",
            "default": 0.35,
            "unit": "ratio",
            "description": "Minimum Saudi share of in-house Executive Management roles.",
        },
        {
            "key": "tenure_threshold_years",
            "default": 5.0,
            "unit": "years",
            "description": (
                "When 'protect_tenured_inhouse' is on, employees with at least this many years "
                "of tenure are protected — they must remain in-house in the optimized headcount."
            ),
        },
        {
            "key": "can_reduce_current_saudi",
            "default": False,
            "unit": "boolean",
            "description": (
                "When False (default), the optimizer must keep at least the current in-house Saudi "
                "headcount per family. When True, the Saudi count can drop below the current level."
            ),
        },
    ]


def _cost_assumptions_section() -> list[dict[str, Any]]:
    return [
        {
            "name": "Overtime cost rate",
            "value": "50 SAR per O.T. hour",
            "description": "When the workbook has an 'O.T Hrs' column, the tool adds 50 SAR per hour to each in-house employee's monthly cost.",
            "implemented_in": "manpower_app/service.py (overtime cost section)",
        },
        {
            "name": "Saudi cost premium",
            "value": "Saudi cost = 1.10 × non-Saudi cost (default; user-overridable)",
            "description": (
                "The fully-loaded cost split assumes Saudis cost 10% more than non-Saudis "
                "in-house when computing per-employee averages from blended workbook data. "
                "Editable per-run via the 'saudi_cost_premium' setting in the Custom assumptions "
                "section of the scenario controls."
            ),
            "implemented_in": "manpower_app/costs.py:calculate_inhouse_cost_split",
            "user_overridable": True,
        },
        {
            "name": "Outsource cost vs. in-house non-Saudi",
            "value": "Workbook-derived by default; user can override as a fraction (1 - discount) of non-Saudi in-house cost",
            "description": (
                "By default, the unit cost of an outsourced FTE comes from the subcontractor "
                "sheet (basic, housing, insurance, service fee, etc). Per-run, the user can "
                "set 'outsource_cost_discount' to replace the workbook value with a fraction "
                "of the non-Saudi in-house cost — useful for what-if analysis when the "
                "workbook costs are not representative of negotiated terms."
            ),
            "implemented_in": "manpower_app/service.py:prepare_model_data (outsource discount override)",
            "user_overridable": True,
        },
        {
            "name": "Service-fee negotiated cap",
            "value": "500 SAR per outsourced FTE",
            "description": (
                "Under the 'negotiated_rates' scenario, outsource service fees per FTE are capped at 500 SAR "
                "(the typical negotiated ceiling). The original (non-negotiated) fee is uncapped."
            ),
            "implemented_in": "manpower_app/service.py (Service_Fee_Negotiated)",
        },
        {
            "name": "Default sponsor insurance fallback",
            "value": "Mapped per sponsor: ewan/mahara/tatweer = 38 SAR, saed azka = 46 SAR, arco = 50 SAR, others = 38 SAR",
            "description": (
                "If the workbook does not explicitly set 'Insurance Costs' for an outsourced row, "
                "the tool assigns a default monthly insurance amount based on the 'Sponser' value."
            ),
            "implemented_in": "manpower_app/costs.py:get_insurance_cost",
        },
        {
            "name": "Fallback in-house cost when no in-house exist",
            "value": "1.20 × Avg Cost Outsourced",
            "description": (
                "For job families with no current in-house workers (so no average cost can be computed), "
                "the tool estimates the fully-loaded in-house cost as 120% of the outsourced unit cost."
            ),
            "implemented_in": "manpower_app/service.py (Fully Loaded Cost per In-house Employee fallback)",
        },
    ]


def _input_format_section() -> dict[str, Any]:
    return {
        "required_sheets": ["Inhouse", "Subcontractor"],
        "required_inhouse_columns": [
            "No",
            "Location",
            "Profession",
            "Nationality",
            "Total Paid",
            "Total Unpaid",
        ],
        "required_subcontractor_columns": [
            "No",
            "Working in",
            "Profession",
            "Nationality",
            "Basic",
        ],
        "nationality_detection": (
            "A row is counted as Saudi when its 'Nationality' value matches 'SAUDI' "
            "(case- and whitespace-insensitive — 'Saudi', 'saudi', ' SAUDI ' all count)."
        ),
        "tenure_detection": (
            "If the inhouse sheet has any of: 'Hire Date', 'Date of Joining', 'Joining Date', "
            "'Start Date', or 'Tenure Years', the tool derives tenure for each employee. "
            "Tenure-protected workers can only be enforced when 'protect_tenured_inhouse' is on."
        ),
    }


def _risk_formula_section() -> dict[str, Any]:
    return {
        "formula": "Outsourced * (1 - risk_factor) + In-house >= Minimum Headcount Needed",
        "description": (
            "For every job family the optimizer must satisfy this constraint. It says an outsourced worker "
            "counts as (1 - risk_factor) of an in-house worker for the purpose of meeting the minimum "
            "headcount needed for the operation to run. Lowering the risk factor increases the share of the "
            "workforce that can be outsourced; raising it forces more in-house staffing."
        ),
        "edge_case_risk_zero": (
            "When risk_factor = 0, an outsourced worker counts as a full in-house worker, so the constraint "
            "becomes always-satisfied. In effect, no in-house floor is enforced from the risk side."
        ),
    }
