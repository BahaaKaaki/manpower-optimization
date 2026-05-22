from __future__ import annotations

import math

import pulp

from manpower_app.rules import HQ_FIXED_INHOUSE_FAMILIES
from manpower_app.terminology import (
    LEGACY_OUTSOURCED_COST_BASIS_COLUMN,
    OUTSOURCED_UNIT_COST_BASIS_COLUMN,
)
from manpower_app.utils import normalize_lookup_text, safe_numeric


OUTSOURCED_COLUMN = "Optimized Outsourced"
IN_HOUSE_NON_SAUDI_COLUMN = "Optimized In-house Non Saudi"
IN_HOUSE_SAUDI_COLUMN = "Optimized In-house Saudi"

# Families with a hardcoded composition rule that ALWAYS overrides the LP's
# cost-minimization. By name these are inherently 100% Saudi.
ALL_SAUDI_FAMILIES = frozenset({"Idle Saudi Labor"})


def _is_all_saudi_family(family) -> bool:
    return str(family or "").strip() in ALL_SAUDI_FAMILIES


def _outsourced_cost_column(data):
    if OUTSOURCED_UNIT_COST_BASIS_COLUMN in data.columns:
        return OUTSOURCED_UNIT_COST_BASIS_COLUMN
    if LEGACY_OUTSOURCED_COST_BASIS_COLUMN in data.columns:
        return LEGACY_OUTSOURCED_COST_BASIS_COLUMN
    return "Avg Cost Outsourced"


def _risk_factor(row):
    risk_factor = safe_numeric(row.get("Risk Factor", 0.25))
    return max(0.0, min(1.0, risk_factor))


def _max_outsourced_allowed(row):
    total_headcount = int(safe_numeric(row.get("Current Headcount")))
    outsourceability_type = row.get("Outsourceability Type")
    job_family = row.get("Job Family")

    max_outsourced = total_headcount
    if outsourceability_type in {"Not Outsourceable", "Fully In-House", "Fully Inhouse"}:
        max_outsourced = 0
    elif outsourceability_type == "Partially Outsourceable":
        if job_family in HQ_FIXED_INHOUSE_FAMILIES:
            hq_inhouse_count = int(safe_numeric(row.get("HQ Inhouse Count")))
            max_outsourced = max(0, total_headcount - hq_inhouse_count)
        else:
            max_outsourced = min(total_headcount, int(safe_numeric(row.get("Outsourced v1"))))

    return min(total_headcount, max(0, max_outsourced))


def _minimum_inhouse_required(row):
    total_headcount = int(safe_numeric(row.get("Current Headcount")))
    minimum_inhouse = int(safe_numeric(row.get("Minimum Headcount Needed")))
    return min(total_headcount, max(0, minimum_inhouse))


def _saudi_lower_bound(
    row,
    *,
    can_reduce_current_saudi,
    tenure_constraint_active,
    protect_current_saudi_percent=None,
):
    """Lower bound for in-house Saudi count per family.

    `protect_current_saudi_percent` (0.0–1.0) is the dynamic-protection field added in
    batch 2 — when supplied it takes precedence over the legacy boolean. The bool path
    is preserved for Streamlit and back-compat callers.

    The result is capped at the target Current Headcount so a Target-mode reduction
    (e.g. target=0 for a family) is always feasible — protection is bounded by what
    the target actually allows."""
    total_headcount = int(safe_numeric(row.get("Current Headcount")))
    current_saudi = int(safe_numeric(row.get("Current Total In-house Saudi")))
    tenured_saudi = (
        int(safe_numeric(row.get("Tenured Saudi In-House"))) if tenure_constraint_active else 0
    )
    if protect_current_saudi_percent is not None:
        pct = max(0.0, min(1.0, safe_numeric(protect_current_saudi_percent)))
        # Round half-up so 50% of 5 = 3 (consultant's spec from screenshot 1's yellow
        # row), not 2 (banker's rounding).
        floor_from_current = math.ceil(current_saudi * pct - 1e-9)
    else:
        floor_from_current = 0 if can_reduce_current_saudi else current_saudi
    raw_lb = max(floor_from_current, tenured_saudi)
    # Cap at total_headcount so e.g. target = 0 or target < current_saudi can still be
    # feasible — the LP's headcount-equality constraint (O + NS + S == total) would
    # otherwise become unsatisfiable.
    return min(total_headcount, raw_lb)


def _non_saudi_lower_bound(row, *, tenure_constraint_active):
    if not tenure_constraint_active:
        return 0
    return int(safe_numeric(row.get("Tenured Non-Saudi In-House")))


def _clamp_results_to_valid_ranges(data):
    """Defensive sanity clamp on solver output: keep counts non-negative and respect headcount."""
    data = data.copy()

    def enforce(row):
        total_headcount = int(safe_numeric(row.get("Current Headcount")))
        saudi = min(total_headcount, max(0, int(safe_numeric(row.get(IN_HOUSE_SAUDI_COLUMN)))))
        max_outsourced = min(_max_outsourced_allowed(row), max(0, total_headcount - saudi))
        outsourced = min(max_outsourced, max(0, int(safe_numeric(row.get(OUTSOURCED_COLUMN)))))
        non_saudi = max(0, total_headcount - saudi - outsourced)
        return outsourced, non_saudi, saudi

    adjusted = data.apply(enforce, axis=1, result_type="expand")
    data[[OUTSOURCED_COLUMN, IN_HOUSE_NON_SAUDI_COLUMN, IN_HOUSE_SAUDI_COLUMN]] = adjusted
    return data


def _calculate_total_payroll(data, outsourced_cost_column):
    return safe_numeric(
        (
            data["Fully Loaded Cost per In-house Saudi Employee"] * data[IN_HOUSE_SAUDI_COLUMN]
            + data["Fully Loaded Cost per In-house Non-Saudi Employee"] * data[IN_HOUSE_NON_SAUDI_COLUMN]
            + data[outsourced_cost_column] * data[OUTSOURCED_COLUMN]
        ).sum()
    )


def solve_optimization(
    data,
    *,
    enforce_saudization,
    saudization_rate,
    can_reduce_current_saudi,
    tenure_constraint_active,
    profession_saudization_rates,
    protect_current_saudi_percent=None,
):
    """Solve the manpower optimization LP and write final headcount columns onto ``data``.

    For each job-family row decide three integer counts that minimize total
    payroll cost subject to:

    * ``Outsourced + NonSaudi + Saudi == Current Headcount`` (per row)
    * ``Outsourced * (1 - risk) + NonSaudi + Saudi >= Minimum Headcount Needed`` (per row)
    * ``Outsourced <= max_outsourced_allowed`` (driven by Outsourceability Type / Outsourced v1 cap)
    * ``Saudi >= current_saudi`` when ``can_reduce_current_saudi`` is False
    * ``Saudi >= tenured_saudi``, ``NonSaudi >= tenured_non_saudi`` when ``tenure_constraint_active`` is True
    * ``sum(Saudi) >= rate * sum(Saudi + NonSaudi)`` when ``enforce_saudization`` is True
    * ``Saudi_i >= profession_rate * (Saudi_i + NonSaudi_i)`` for each job family that has a
      profession rate set in ``profession_saudization_rates``

    Returns ``(data, total_payroll, status)``. On a non-Optimal solver status the function
    falls back to the current state (Current Outsourced / In-House Non-Saudi / Total Saudi).
    """
    data = data.copy()
    outsourced_cost_column = _outsourced_cost_column(data)

    prob = pulp.LpProblem("Manpower_Optimization", pulp.LpMinimize)
    outsourced_vars: list[pulp.LpVariable] = []
    non_saudi_vars: list[pulp.LpVariable] = []
    saudi_vars: list[pulp.LpVariable] = []

    # "Strict zero Saudi" applies when the user explicitly drops Saudization to 0
    # AND allows reducing current Saudis. Without this, the LP keeps existing
    # Saudis whenever they happen to be cheaper — confusing to users who set
    # 0% expecting "no Saudis". Tenure protection still wins (no eviction of
    # tenured staff). Explicit dynamic protection (>0%) also takes precedence —
    # the user can't simultaneously ask to keep 60% of Saudis AND drive to zero.
    strict_zero_saudi = (
        enforce_saudization
        and safe_numeric(saudization_rate) <= 0
        and can_reduce_current_saudi
        and not tenure_constraint_active
        and (
            protect_current_saudi_percent is None
            or safe_numeric(protect_current_saudi_percent) <= 0
        )
    )

    for i, row in data.iterrows():
        total_headcount = int(safe_numeric(row["Current Headcount"]))
        family = row.get("Job Family")
        profession_rate = profession_saudization_rates.get(normalize_lookup_text(family))
        has_profession_rate_above_zero = (
            profession_rate is not None and safe_numeric(profession_rate) > 0
        )

        # Family-specific overrides applied BEFORE any LP variables are built so
        # they win over every other constraint:
        #   • Idle Saudi Labor → all-Saudi by definition.
        if _is_all_saudi_family(family):
            max_outsourced = 0
            non_saudi_lb = 0
            non_saudi_ub = 0
            saudi_lb = total_headcount
            saudi_ub = total_headcount
        elif total_headcount == 0:
            # Target mode allows the user to zero a family's headcount. The
            # headcount-equality constraint then forces O + NS + S = 0, so every
            # lower bound must collapse to 0 to keep the LP feasible. Saudi
            # protection / tenure / minimum-inhouse are all bounded by total
            # headcount, so this is consistent.
            max_outsourced = 0
            non_saudi_lb = 0
            non_saudi_ub = 0
            saudi_lb = 0
            saudi_ub = 0
        else:
            max_outsourced = _max_outsourced_allowed(row)
            saudi_lb = _saudi_lower_bound(
                row,
                can_reduce_current_saudi=can_reduce_current_saudi,
                tenure_constraint_active=tenure_constraint_active,
                protect_current_saudi_percent=protect_current_saudi_percent,
            )
            non_saudi_lb = _non_saudi_lower_bound(row, tenure_constraint_active=tenure_constraint_active)
            non_saudi_ub = None
            # Strict-zero override: force Saudi count to 0 when the user set
            # Saudization = 0 with protection off, EXCEPT for families with an
            # explicit profession-level rate > 0 (which still need Saudis to
            # meet their per-family minimum).
            family_strict_zero = strict_zero_saudi and not has_profession_rate_above_zero
            saudi_ub = 0 if family_strict_zero else None

        outsourced = pulp.LpVariable(f"Outsourced_{i}", lowBound=0, upBound=max_outsourced, cat="Integer")
        non_saudi = pulp.LpVariable(f"NonSaudi_{i}", lowBound=non_saudi_lb, upBound=non_saudi_ub, cat="Integer")
        saudi = pulp.LpVariable(f"Saudi_{i}", lowBound=saudi_lb, upBound=saudi_ub, cat="Integer")

        outsourced_vars.append(outsourced)
        non_saudi_vars.append(non_saudi)
        saudi_vars.append(saudi)

        prob += outsourced + non_saudi + saudi == total_headcount, f"Total_Headcount_{i}"

        minimum_inhouse = _minimum_inhouse_required(row)
        risk = _risk_factor(row)
        prob += outsourced * (1 - risk) + non_saudi + saudi >= minimum_inhouse, f"Risk_Adjusted_Minimum_{i}"

        profession_rate = profession_saudization_rates.get(
            normalize_lookup_text(row.get("Job Family"))
        )
        if profession_rate is not None:
            prob += saudi >= safe_numeric(profession_rate) * (saudi + non_saudi), f"Profession_Saudization_{i}"

    prob += pulp.lpSum(
        data.iloc[i][outsourced_cost_column] * outsourced_vars[i]
        + data.iloc[i]["Fully Loaded Cost per In-house Non-Saudi Employee"] * non_saudi_vars[i]
        + data.iloc[i]["Fully Loaded Cost per In-house Saudi Employee"] * saudi_vars[i]
        for i in range(len(data))
    )

    if enforce_saudization:
        prob += pulp.lpSum(saudi_vars) >= safe_numeric(saudization_rate) * pulp.lpSum(
            saudi_vars[i] + non_saudi_vars[i] for i in range(len(data))
        ), "Global_Saudization_Rate"

    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    status = pulp.LpStatus[prob.status]

    if status == "Optimal":
        data[OUTSOURCED_COLUMN] = [int(var.varValue) for var in outsourced_vars]
        data[IN_HOUSE_NON_SAUDI_COLUMN] = [int(var.varValue) for var in non_saudi_vars]
        data[IN_HOUSE_SAUDI_COLUMN] = [int(var.varValue) for var in saudi_vars]
    else:
        data[OUTSOURCED_COLUMN] = data["Current Outsourced Count"].apply(lambda x: int(safe_numeric(x)))
        data[IN_HOUSE_NON_SAUDI_COLUMN] = data["Current In-House Non-Saudi Count"].apply(lambda x: int(safe_numeric(x)))
        data[IN_HOUSE_SAUDI_COLUMN] = data["Current Total In-house Saudi"].apply(lambda x: int(safe_numeric(x)))

    data = _clamp_results_to_valid_ranges(data)
    return data, _calculate_total_payroll(data, outsourced_cost_column), status
