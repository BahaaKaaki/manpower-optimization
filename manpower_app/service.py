from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, BinaryIO

import pandas as pd

from manpower_app.costs import (
    calculate_inhouse_cost_split,
    calculate_inhouse_fully_loaded_employee_cost,
    calculate_outsource_base_employee_cost,
    calculate_outsource_employee_cost,
    cap_outsourced_at_inhouse,
)
from manpower_app.costs import bump_inhouse_non_saudi_above_outsourced
from manpower_app.export import build_results_workbook
from manpower_app.family_specs import (
    CustomFamilySpec,
    custom_families_by_name,
    merge_user_mappings,
)
from manpower_app.mappings import (
    JOB_FAMILY_MAPPING,
    NORMALIZED_ACTIVITY_MAPPING,
    NORMALIZED_PROFESSION_MAPPING,
    get_job_family_with_fallback,
)
from manpower_app.optimization import (
    IN_HOUSE_NON_SAUDI_COLUMN,
    IN_HOUSE_SAUDI_COLUMN,
    OUTSOURCED_COLUMN,
    solve_optimization,
)
from manpower_app.pipeline import read_manpower_workbook
from manpower_app.ratios import (
    build_current_ratio_display,
    calculate_driver_values,
    calculate_minimum_headcount_needed,
    calculate_outsourced_v1,
    calculate_partial_config_minimum,
    load_ratio_rules,
    lookup_ratio_rule,
    resolve_average_costs,
)
from manpower_app.results import build_optimized_results
from manpower_app.rules import (
    MAXIMUM_RATIO_RULES,
    OUTSOURCEABILITY_RULES,
    get_maximum_ratio_rules,
    get_outsourceability_rules,
)
from manpower_app.terminology import (
    FINAL_SCENARIO_LABEL,
    LEGACY_OUTSOURCED_COST_BASIS_COLUMN,
    OPTIMIZATION_STATUS_KEY,
    OPTIMIZED_PAYROLL_KEY,
    OPTIMIZED_SAVINGS_KEY,
    OUTSOURCED_UNIT_COST_BASIS_COLUMN,
)
from manpower_app.tenure import (
    derive_tenure_years,
    detect_tenure_column,
    summarize_tenured_inhouse,
)
from manpower_app.utils import (
    clean_lookup_text,
    detect_service_fee_column,
    is_blank,
    normalize_lookup_text,
    safe_divide,
    safe_numeric,
)


@dataclass
class ProcessedWorkbook:
    optimization_df: pd.DataFrame
    inhouse_cleaned: pd.DataFrame
    subcontractor_cleaned: pd.DataFrame
    service_fee_column: str | None
    tenure_source_column: str | None
    unmapped_pairs: list[dict[str, Any]] = field(default_factory=list)
    workbook_pairs: list[dict[str, str]] = field(default_factory=list)
    # Phase 3: True when the uploaded Inhouse sheet has the optional
    # "Manpower Performance" column. When False the engine still runs (every
    # row defaults to 3.0) but the UI disables the high-performer protection
    # toggle and shows a "scores missing" caption.
    has_performance_column: bool = False


@dataclass
class OptimizationSettings:
    enforce_saudization: bool = True
    saudization_rate: float = 0.30
    can_reduce_current_saudi: bool = False
    # Dynamic Saudi protection (0.0–1.0). When set, overrides the boolean above and
    # protects that fraction of current Saudis per family. 1.0 = today's "Protect on";
    # 0.0 = today's "Protect off"; anything in between is partial protection.
    protect_current_saudi_percent: float | None = None
    risk_factor: float = 0.25
    negotiated_rates: bool = False
    negotiated_insurance_cost: float = 0.0
    negotiated_service_margin: float = 0.0
    protect_tenured_inhouse: bool = False
    tenure_threshold_years: float = 5.0
    engineer_saudization_rate: float = 0.25
    sales_saudization_rate: float = 0.60
    management_saudization_rate: float = 0.35
    # Executive Management has its own input separate from the broader Management
    # family per consultant feedback — the two were previously controlled by a single
    # rate which led to one input affecting both.
    executive_management_saudization_rate: float = 0.35
    # Phase 3: protect high-performing in-house employees from being outsourced.
    # When ON (Current mode only), each in-house employee with
    # `Manpower Performance >= high_performer_threshold` is treated as a per-family
    # in-house floor that the LP must respect (separately for Saudis and Non-Saudis).
    protect_high_performers: bool = False
    high_performer_threshold: float = 4.0
    # Soft-input overrides for normally-hardcoded assumptions. Defaults preserve historical behavior.
    saudi_cost_premium: float = 1.10
    outsource_cost_discount: float | None = None
    max_ratio_overrides: dict[str, str] = field(default_factory=dict)
    # Batch-2 per-BU configuration overrides. Empty defaults preserve historical behavior.
    outsourceability_overrides: dict[str, str] = field(default_factory=dict)
    driver_overrides: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    # Per-BU mapping pipeline overrides (sourced from the BU's Excel). Carried on the
    # settings object so they flow through prepare_model_data and run_optimization;
    # process_workbook uses them on the first pass via separate kwargs at upload time.
    activity_mapping: dict[str, str] = field(default_factory=dict)
    profession_mapping: dict[str, str] = field(default_factory=dict)
    job_family_mapping: dict[str, str] = field(default_factory=dict)
    # Tier 5: target manpower plan mode. Empty defaults preserve historical behavior.
    optimization_mode: str = "current"  # "current" | "target"
    target_headcounts: dict[str, int] = field(default_factory=dict)
    custom_families: list[CustomFamilySpec] = field(default_factory=list)


def dataframe_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    safe_df = df.copy().astype(object)
    safe_df = safe_df.where(pd.notna(safe_df), None)
    return safe_df.to_dict(orient="records")


def _collect_unmapped_pairs(
    inhouse_unmapped: pd.DataFrame,
    subcontractor_unmapped: pd.DataFrame,
) -> list[dict[str, Any]]:
    """Aggregate unmapped (activity, profession) pairs across both sheets."""
    parts = []
    for source, df in (("inhouse", inhouse_unmapped), ("subcontractor", subcontractor_unmapped)):
        if df is None or df.empty:
            continue
        sub = df[["Activity_Standardized", "Profession_Standardized"]].copy()
        sub = sub.assign(source=source)
        parts.append(sub)
    if not parts:
        return []
    combined = pd.concat(parts, ignore_index=True)
    grouped = (
        combined.groupby(["Activity_Standardized", "Profession_Standardized"])
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    return [
        {
            "activity": str(row["Activity_Standardized"]),
            "profession": str(row["Profession_Standardized"]),
            "count": int(row["count"]),
        }
        for _, row in grouped.iterrows()
    ]


def _collect_workbook_pairs(
    inhouse_df: pd.DataFrame,
    subcontractor_df: pd.DataFrame,
) -> list[dict[str, str]]:
    """Distinct (activity, profession) pairs present in the workbook.

    Used by the desktop UI to populate dropdowns when the user defines a driver-based
    family (the driver activity + profession must come from values that actually exist
    in the workbook).
    """
    parts = []
    for df in (inhouse_df, subcontractor_df):
        if df is None or df.empty:
            continue
        sub = df[["Activity_Standardized", "Profession_Standardized"]].copy()
        sub = sub[
            sub["Activity_Standardized"].astype(str).str.strip().ne("")
            & sub["Profession_Standardized"].astype(str).str.strip().ne("")
        ]
        parts.append(sub)
    if not parts:
        return []
    combined = pd.concat(parts, ignore_index=True).drop_duplicates()
    combined = combined.sort_values(["Activity_Standardized", "Profession_Standardized"])
    return [
        {"activity": str(row["Activity_Standardized"]), "profession": str(row["Profession_Standardized"])}
        for _, row in combined.iterrows()
    ]


def _inject_custom_family_rows(
    optimization_df: pd.DataFrame,
    custom_families: list[CustomFamilySpec],
) -> pd.DataFrame:
    """Append rows for user-defined families that have no entries in the workbook.

    These are "brand new" families the user is introducing for target-mode planning. The
    user must have supplied costs (Saudi in-house / non-Saudi in-house / outsourced); the
    headcount columns start at zero and ``prepare_model_data`` will overwrite ``Current
    Headcount`` with the user's target if target mode is active.
    """
    existing_families = set(optimization_df["Job Family"]) if not optimization_df.empty else set()
    new_rows: list[dict[str, Any]] = []
    for spec in custom_families:
        if spec.family_name in existing_families:
            continue
        if spec.costs is None:
            # Brand-new family without costs is not actionable; skip silently. The UI must
            # require costs before letting the user save such a family.
            continue
        new_rows.append({
            "Job Family": spec.family_name,
            "Outsourceability Type": spec.outsourceability,
            "Driver Value": pd.NA,
            "Current Ratio": "—",
            "Maximum Ratio": (
                spec.partial_config.max_ratio
                if spec.partial_config and spec.partial_config.kind == "driver" and spec.partial_config.max_ratio
                else "N/A"
            ),
            "Minimum Headcount Needed": 0,
            "Current Outsourced Ratio": 0.0,
            "Avg Cost Non-Saudi Inhouse": float(spec.costs.non_saudi_inhouse),
            "Avg Cost Saudi Inhouse": float(spec.costs.saudi_inhouse),
            "Avg Cost Outsourced": float(spec.costs.outsourced),
            "Avg Cost Outsourced Original": float(spec.costs.outsourced),
            "Avg Cost Outsourced Negotiated": float(spec.costs.outsourced),
            "Avg Outsourced Base Cost Excluding Insurance Service": pd.NA,
            "Fully Loaded Cost per In-house Employee": float(spec.costs.non_saudi_inhouse),
            "Current Headcount": 0,
            "Current In-House Count": 0,
            "Current Outsourced Count": 0,
            "Current Total In-house Saudi": 0,
            "Current In-House Non-Saudi Count": 0,
            "HQ Inhouse Count": 0,
            "Max Outsource Ratio": (
                "100%" if spec.outsourceability == "Fully Outsourceable"
                else "0%" if spec.outsourceability == "Not Outsourceable"
                else "TBD"
            ),
            "Max Outsource Ratio Value": (
                1.0 if spec.outsourceability == "Fully Outsourceable"
                else 0.0 if spec.outsourceability == "Not Outsourceable"
                else 0.5
            ),
        })
    if not new_rows:
        return optimization_df
    return pd.concat([optimization_df, pd.DataFrame(new_rows)], ignore_index=True)


def process_workbook(
    excel_source: str | BinaryIO,
    *,
    custom_families: list[CustomFamilySpec] | None = None,
    payroll_pair_overrides: dict[str, str] | None = None,
    activity_mapping_overrides: dict[str, str] | None = None,
    profession_mapping_overrides: dict[str, str] | None = None,
    job_family_mapping_overrides: dict[str, str] | None = None,
) -> ProcessedWorkbook:
    """
    `payroll_pair_overrides`: maps "<activity>|<profession>" keys directly to a canonical
    job family name, so the user can route a new profession (e.g. "senior labor") to an
    existing family ("Labor") without creating a brand-new custom family.

    `activity_mapping_overrides`, `profession_mapping_overrides`, and
    `job_family_mapping_overrides`: per-BU overlays on the hardcoded ``mappings.py``
    pipeline. Allow a Business Unit to define raw->standardized translations and
    activity-profession -> family routing specific to its operations. Each is layered
    ON TOP of the hardcoded defaults; missing entries fall back to defaults.
    """
    custom_families = custom_families or []
    custom_by_name = custom_families_by_name(custom_families)

    # Build the effective activity and profession mappings: hardcoded defaults overlaid
    # with the BU-supplied overrides. Both lookups use the normalized key form to be
    # case- and whitespace-insensitive.
    effective_activity_mapping = dict(NORMALIZED_ACTIVITY_MAPPING)
    if activity_mapping_overrides:
        for raw, standardized in activity_mapping_overrides.items():
            if isinstance(raw, str) and isinstance(standardized, str) and standardized.strip():
                effective_activity_mapping[normalize_lookup_text(raw)] = standardized.strip()

    effective_profession_mapping = dict(NORMALIZED_PROFESSION_MAPPING)
    if profession_mapping_overrides:
        for raw, standardized in profession_mapping_overrides.items():
            if isinstance(raw, str) and isinstance(standardized, str) and standardized.strip():
                effective_profession_mapping[normalize_lookup_text(raw)] = standardized.strip()

    # Build the effective job-family mapping: hardcoded defaults, user-defined custom
    # families, BU-supplied job-family overrides, and the per-pair overrides layered in
    # that order. Later overlays win.
    effective_job_family_mapping = merge_user_mappings(JOB_FAMILY_MAPPING, custom_families)
    if job_family_mapping_overrides:
        for pair_key, family in job_family_mapping_overrides.items():
            if isinstance(pair_key, str) and isinstance(family, str) and family.strip():
                effective_job_family_mapping = {
                    **effective_job_family_mapping,
                    pair_key: family.strip(),
                }
    if payroll_pair_overrides:
        for raw_key, family in payroll_pair_overrides.items():
            if not isinstance(raw_key, str) or "|" not in raw_key:
                continue
            activity, profession = raw_key.split("|", 1)
            cleaned_pair = f"{clean_lookup_text(activity)} - {clean_lookup_text(profession)}"
            effective_job_family_mapping = {
                **effective_job_family_mapping,
                cleaned_pair: family,
            }

    inhouse_df, subcontractor_df = read_manpower_workbook(excel_source)

    inhouse_df = inhouse_df[
        ~(
            inhouse_df["No"].apply(is_blank)
            & inhouse_df["Location"].apply(is_blank)
            & inhouse_df["Profession"].apply(is_blank)
            & inhouse_df["Nationality"].apply(is_blank)
        )
    ].copy()
    subcontractor_df = subcontractor_df[
        ~(
            subcontractor_df["No"].apply(is_blank)
            & subcontractor_df["Working in"].apply(is_blank)
            & subcontractor_df["Profession"].apply(is_blank)
            & subcontractor_df["Nationality"].apply(is_blank)
        )
    ].copy()

    inhouse_df["Activity_Standardized"] = inhouse_df["Location"].apply(
        lambda x: effective_activity_mapping.get(normalize_lookup_text(x), clean_lookup_text(x))
    )
    inhouse_df["Profession_Standardized"] = inhouse_df["Profession"].apply(
        lambda x: effective_profession_mapping.get(normalize_lookup_text(x), clean_lookup_text(x))
    )
    inhouse_df["Activity_Profession"] = (
        inhouse_df["Activity_Standardized"] + " - " + inhouse_df["Profession_Standardized"]
    )
    inhouse_df["Job_Family"] = inhouse_df["Activity_Profession"].apply(
        lambda x: get_job_family_with_fallback(x, effective_job_family_mapping)
    )
    inhouse_valid_for_mapping = (
        inhouse_df["Activity_Standardized"].astype(str).str.strip().ne("")
        & inhouse_df["Profession_Standardized"].astype(str).str.strip().ne("")
    )
    inhouse_unmapped_mask = inhouse_df["Job_Family"].isna() & inhouse_valid_for_mapping
    inhouse_unmapped = inhouse_df[inhouse_unmapped_mask].copy()
    # Drop unmapped rows from the working frame so downstream aggregation doesn't choke on NaN
    # job families. The unmapped pairs are still surfaced in ProcessedWorkbook.unmapped_pairs
    # so the UI can prompt the user to resolve them.
    inhouse_df = inhouse_df[~inhouse_unmapped_mask].copy()

    inhouse_df["Is_Saudi"] = (
        inhouse_df["Nationality"].astype(str).str.strip().str.upper() == "SAUDI"
    ).astype(int)
    # Phase 3: read the optional "Manpower Performance" score per employee (1-5).
    # Missing or non-numeric values default to 3 (neutral). Carried through to
    # inhouse_cleaned so the LP layer can count per-family high performers at
    # the user's chosen threshold (Workforce Protection setting).
    has_performance_column = "Manpower Performance" in inhouse_df.columns
    if has_performance_column:
        inhouse_df["Manpower Performance"] = (
            pd.to_numeric(inhouse_df["Manpower Performance"], errors="coerce")
            .fillna(3.0)
            .clip(lower=1.0, upper=5.0)
        )
    else:
        inhouse_df["Manpower Performance"] = 3.0
    inhouse_df["Cost_Per_Employee"] = inhouse_df["Total Paid"] + inhouse_df["Total Unpaid"]
    inhouse_df["Fully_Loaded_Inhouse_Cost_Per_Employee"] = inhouse_df.apply(
        calculate_inhouse_fully_loaded_employee_cost,
        axis=1,
    )
    inhouse_df["Saudi_Cost_Per_Employee"] = inhouse_df["Cost_Per_Employee"] * inhouse_df["Is_Saudi"]
    inhouse_df["Non_Saudi_Cost_Per_Employee"] = (
        inhouse_df["Cost_Per_Employee"] * (1 - inhouse_df["Is_Saudi"])
    )

    if "O.T Hrs" in inhouse_df.columns:
        overtime_cost = inhouse_df["O.T Hrs"].fillna(0) * 50
        inhouse_df["Cost_Per_Employee"] += overtime_cost
        inhouse_df["Saudi_Cost_Per_Employee"] += overtime_cost * inhouse_df["Is_Saudi"]
        inhouse_df["Non_Saudi_Cost_Per_Employee"] += overtime_cost * (1 - inhouse_df["Is_Saudi"])

    tenure_source_column, tenure_source_mode = detect_tenure_column(inhouse_df.columns)
    inhouse_df["Tenure Years"] = (
        derive_tenure_years(inhouse_df[tenure_source_column], tenure_source_mode)
        if tenure_source_column
        else pd.Series(index=inhouse_df.index, dtype="float64")
    )
    inhouse_df["Tenure Source Column"] = tenure_source_column if tenure_source_column else ""
    inhouse_df["Tenure Source Mode"] = tenure_source_mode if tenure_source_mode else ""

    inhouse_summary = inhouse_df.groupby("Job_Family").agg({
        "No": "count",
        "Is_Saudi": "sum",
        "Cost_Per_Employee": "sum",
        "Fully_Loaded_Inhouse_Cost_Per_Employee": "sum",
        "Saudi_Cost_Per_Employee": "sum",
        "Non_Saudi_Cost_Per_Employee": "sum",
    }).rename(columns={"No": "Total_Inhouse", "Is_Saudi": "Saudi_Inhouse"})
    inhouse_summary["Non_Saudi_Inhouse"] = (
        inhouse_summary["Total_Inhouse"] - inhouse_summary["Saudi_Inhouse"]
    )
    hq_inhouse_counts = (
        inhouse_df[inhouse_df["Activity_Standardized"] == "Head Office"]
        .groupby("Job_Family")
        .size()
        .rename("HQ_Inhouse_Count")
    )
    inhouse_summary = inhouse_summary.join(hq_inhouse_counts, how="left")
    inhouse_summary["HQ_Inhouse_Count"] = (
        inhouse_summary["HQ_Inhouse_Count"].fillna(0).astype(int)
    )
    inhouse_summary["Avg_Cost_Saudi_Inhouse"] = inhouse_summary.apply(
        lambda row: row["Saudi_Cost_Per_Employee"] / row["Saudi_Inhouse"]
        if row["Saudi_Inhouse"] > 0
        else 0,
        axis=1,
    )
    inhouse_summary["Avg_Cost_NonSaudi_Inhouse"] = inhouse_summary.apply(
        lambda row: row["Non_Saudi_Cost_Per_Employee"] / row["Non_Saudi_Inhouse"]
        if row["Non_Saudi_Inhouse"] > 0
        else 0,
        axis=1,
    )
    inhouse_summary["Fully_Loaded_Cost_Per_Inhouse_Employee"] = inhouse_summary.apply(
        lambda row: row["Fully_Loaded_Inhouse_Cost_Per_Employee"] / row["Total_Inhouse"]
        if row["Total_Inhouse"] > 0
        else 0,
        axis=1,
    )

    subcontractor_df["Activity_Standardized"] = subcontractor_df["Working in"].apply(
        lambda x: effective_activity_mapping.get(normalize_lookup_text(x), clean_lookup_text(x))
    )
    subcontractor_df["Profession_Standardized"] = subcontractor_df["Profession"].apply(
        lambda x: effective_profession_mapping.get(normalize_lookup_text(x), clean_lookup_text(x))
    )
    subcontractor_df["Activity_Profession"] = (
        subcontractor_df["Activity_Standardized"] + " - " + subcontractor_df["Profession_Standardized"]
    )
    subcontractor_df["Job_Family"] = subcontractor_df["Activity_Profession"].apply(
        lambda x: get_job_family_with_fallback(x, effective_job_family_mapping)
    )
    subcontractor_valid_for_mapping = (
        subcontractor_df["Activity_Standardized"].astype(str).str.strip().ne("")
        & subcontractor_df["Profession_Standardized"].astype(str).str.strip().ne("")
    )
    subcontractor_unmapped_mask = subcontractor_df["Job_Family"].isna() & subcontractor_valid_for_mapping
    subcontractor_unmapped = subcontractor_df[subcontractor_unmapped_mask].copy()
    subcontractor_df = subcontractor_df[~subcontractor_unmapped_mask].copy()

    unmapped_pairs = _collect_unmapped_pairs(inhouse_unmapped, subcontractor_unmapped)

    subcontractor_df["Is_Saudi"] = (
        subcontractor_df["Nationality"].astype(str).str.strip().str.upper() == "SAUDI"
    ).astype(int)
    service_fee_column = detect_service_fee_column(subcontractor_df.columns)
    subcontractor_df["Service_Fee_Original"] = (
        subcontractor_df[service_fee_column].apply(safe_numeric) if service_fee_column else 0.0
    )
    subcontractor_df["Service_Fee_Negotiated"] = subcontractor_df["Service_Fee_Original"].apply(
        lambda value: min(value, 500.0)
    )
    subcontractor_df["Negotiated_Service_Fee_Savings"] = (
        subcontractor_df["Service_Fee_Original"] - subcontractor_df["Service_Fee_Negotiated"]
    )
    subcontractor_df["Outsource_Base_Cost_Excluding_Insurance_Service"] = subcontractor_df.apply(
        calculate_outsource_base_employee_cost,
        axis=1,
    )
    subcontractor_df["Cost_Per_Employee"] = subcontractor_df.apply(
        lambda row: calculate_outsource_employee_cost(
            row,
            service_fee_column=service_fee_column,
            negotiated_service_margin=False,
        ),
        axis=1,
    )
    subcontractor_df["Negotiated_Cost_Per_Employee"] = subcontractor_df.apply(
        lambda row: calculate_outsource_employee_cost(
            row,
            service_fee_column=service_fee_column,
            negotiated_service_margin=True,
        ),
        axis=1,
    )
    subcontractor_summary = subcontractor_df.groupby("Job_Family").agg({
        "No": "count",
        "Is_Saudi": "sum",
        "Outsource_Base_Cost_Excluding_Insurance_Service": "sum",
        "Cost_Per_Employee": "sum",
        "Negotiated_Cost_Per_Employee": "sum",
    }).rename(columns={"No": "Total_Outsourced", "Is_Saudi": "Saudi_Outsourced"})
    subcontractor_summary["Cost_Outsourced"] = subcontractor_summary["Cost_Per_Employee"]
    subcontractor_summary["Avg_Cost_Per_Employee"] = subcontractor_summary.apply(
        lambda row: row["Cost_Per_Employee"] / row["Total_Outsourced"]
        if row["Total_Outsourced"] > 0
        else 0,
        axis=1,
    )
    subcontractor_summary["Avg_Base_Cost_Excluding_Insurance_Service"] = subcontractor_summary.apply(
        lambda row: row["Outsource_Base_Cost_Excluding_Insurance_Service"] / row["Total_Outsourced"]
        if row["Total_Outsourced"] > 0
        else 0,
        axis=1,
    )
    subcontractor_summary["Avg_Negotiated_Cost_Per_Employee"] = subcontractor_summary.apply(
        lambda row: row["Negotiated_Cost_Per_Employee"] / row["Total_Outsourced"]
        if row["Total_Outsourced"] > 0
        else 0,
        axis=1,
    )

    mapped_workforce_df = pd.concat(
        [
            inhouse_df[["Activity_Standardized", "Profession_Standardized", "Job_Family"]],
            subcontractor_df[["Activity_Standardized", "Profession_Standardized", "Job_Family"]],
        ],
        ignore_index=True,
    )
    current_driver_values = calculate_driver_values(mapped_workforce_df)
    ratio_rules_df = load_ratio_rules()
    ratio_rules = ratio_rules_df.set_index("Job Family Key").to_dict("index") if not ratio_rules_df.empty else {}
    all_job_families = set(inhouse_summary.index) | set(subcontractor_summary.index)
    optimization_data: list[dict[str, Any]] = []

    for job_family in sorted(all_job_families):
        inhouse_row = inhouse_summary.loc[job_family] if job_family in inhouse_summary.index else None
        outsource_row = subcontractor_summary.loc[job_family] if job_family in subcontractor_summary.index else None
        total_inhouse = inhouse_row["Total_Inhouse"] if inhouse_row is not None else 0
        total_outsourced = outsource_row["Total_Outsourced"] if outsource_row is not None else 0
        total_employees = total_inhouse + total_outsourced
        total_inhouse_saudi = int(inhouse_row["Saudi_Inhouse"]) if inhouse_row is not None else 0
        total_inhouse_non_saudi = int(total_inhouse - total_inhouse_saudi)
        hq_inhouse_count = int(inhouse_row["HQ_Inhouse_Count"]) if inhouse_row is not None else 0
        avg_cost_inhouse_saudi = inhouse_row["Avg_Cost_Saudi_Inhouse"] if inhouse_row is not None else 0
        avg_cost_inhouse_non_saudi = inhouse_row["Avg_Cost_NonSaudi_Inhouse"] if inhouse_row is not None else 0
        fully_loaded_cost_inhouse = (
            inhouse_row["Fully_Loaded_Cost_Per_Inhouse_Employee"] if inhouse_row is not None else 0
        )
        avg_cost_outsourced = outsource_row["Avg_Cost_Per_Employee"] if outsource_row is not None else 0
        avg_outsource_base_cost = (
            outsource_row["Avg_Base_Cost_Excluding_Insurance_Service"]
            if outsource_row is not None
            else pd.NA
        )
        avg_cost_outsourced_negotiated = (
            outsource_row["Avg_Negotiated_Cost_Per_Employee"] if outsource_row is not None else 0
        )
        ratio_rule, _, _ = lookup_ratio_rule(job_family, ratio_rules)
        custom_spec = custom_by_name.get(job_family)
        if custom_spec is not None:
            outsourceability_type = custom_spec.outsourceability
        else:
            outsourceability_type = OUTSOURCEABILITY_RULES.get(job_family, "Partially Outsourceable")
        driver_value = ratio_rule.get("Driver Value")
        driver_value = current_driver_values[job_family] if job_family in current_driver_values else pd.NA
        current_outsourced_ratio = safe_divide(total_outsourced, total_employees)
        maximum_ratio = MAXIMUM_RATIO_RULES.get(job_family, "N/A")
        minimum_headcount_needed = calculate_minimum_headcount_needed(
            total_employees,
            outsourceability_type,
            driver_value,
            maximum_ratio,
            total_inhouse,
        )

        if outsourceability_type == "Fully Outsourceable":
            max_outsource_ratio = "100%"
            max_outsource_ratio_value = 1.0
        elif outsourceability_type == "Not Outsourceable":
            max_outsource_ratio = "0%"
            max_outsource_ratio_value = 0.0
        else:
            max_outsource_ratio = "TBD"
            max_outsource_ratio_value = current_outsourced_ratio if job_family in {"Administration", "Engineer"} else 0.5

        if total_employees > 0:
            optimization_data.append({
                "Job Family": job_family,
                "Outsourceability Type": outsourceability_type,
                "Driver Value": driver_value,
                "Current Ratio": build_current_ratio_display(total_employees, driver_value),
                "Maximum Ratio": maximum_ratio,
                "Minimum Headcount Needed": minimum_headcount_needed,
                "Current Outsourced Ratio": safe_numeric(current_outsourced_ratio),
                "Avg Cost Non-Saudi Inhouse": avg_cost_inhouse_non_saudi,
                "Avg Cost Saudi Inhouse": avg_cost_inhouse_saudi,
                "Avg Cost Outsourced": avg_cost_outsourced,
                "Avg Cost Outsourced Original": avg_cost_outsourced,
                "Avg Cost Outsourced Negotiated": avg_cost_outsourced_negotiated,
                "Avg Outsourced Base Cost Excluding Insurance Service": avg_outsource_base_cost,
                "Fully Loaded Cost per In-house Employee": fully_loaded_cost_inhouse,
                "Current Headcount": int(total_employees),
                "Current In-House Count": int(total_inhouse),
                "Current Outsourced Count": int(total_outsourced),
                "Current Total In-house Saudi": total_inhouse_saudi,
                "Current In-House Non-Saudi Count": int(total_inhouse_non_saudi),
                "HQ Inhouse Count": hq_inhouse_count,
                "Max Outsource Ratio": max_outsource_ratio,
                "Max Outsource Ratio Value": max_outsource_ratio_value,
            })

    optimization_df = pd.DataFrame(optimization_data)
    resolved_avg_costs = optimization_df.apply(
        lambda row: resolve_average_costs(
            row["Avg Cost Saudi Inhouse"],
            row["Avg Cost Non-Saudi Inhouse"],
            row["Avg Cost Outsourced"],
        ),
        axis=1,
    )
    optimization_df[["Avg Cost Saudi Inhouse", "Avg Cost Non-Saudi Inhouse", "Avg Cost Outsourced"]] = (
        resolved_avg_costs
    )
    if "Avg Cost Outsourced Negotiated" in optimization_df.columns:
        optimization_df["Avg Cost Outsourced Negotiated"] = optimization_df.apply(
            lambda row: resolve_average_costs(
                row["Avg Cost Saudi Inhouse"],
                row["Avg Cost Non-Saudi Inhouse"],
                row["Avg Cost Outsourced Negotiated"],
            )["Avg Cost Outsourced"],
            axis=1,
        )
    if "Avg Cost Outsourced Original" in optimization_df.columns:
        optimization_df["Avg Cost Outsourced Original"] = optimization_df["Avg Cost Outsourced"]
    optimization_df["Fully Loaded Cost per In-house Employee"] = optimization_df.apply(
        lambda row: 1.2 * safe_numeric(row["Avg Cost Outsourced"])
        if safe_numeric(row.get("Current In-House Count")) == 0
        else safe_numeric(row.get("Fully Loaded Cost per In-house Employee")),
        axis=1,
    )
    optimization_df[
        [
            "Fully Loaded Cost per In-house Non-Saudi Employee",
            "Fully Loaded Cost per In-house Saudi Employee",
        ]
    ] = optimization_df.apply(
        lambda row: calculate_inhouse_cost_split(
            row["Fully Loaded Cost per In-house Employee"],
            row["Current Total In-house Saudi"],
            row["Current In-House Non-Saudi Count"],
        ),
        axis=1,
    )

    # Append rows for user-defined families that have no payroll entries (target-mode use).
    optimization_df = _inject_custom_family_rows(optimization_df, custom_families)
    workbook_pairs = _collect_workbook_pairs(inhouse_df, subcontractor_df)

    return ProcessedWorkbook(
        optimization_df=optimization_df,
        inhouse_cleaned=inhouse_df,
        subcontractor_cleaned=subcontractor_df,
        service_fee_column=service_fee_column,
        tenure_source_column=tenure_source_column,
        unmapped_pairs=unmapped_pairs,
        workbook_pairs=workbook_pairs,
        has_performance_column=has_performance_column,
    )


def prepare_model_data(
    processed: ProcessedWorkbook,
    settings: OptimizationSettings,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    # R=0 is supported end-to-end: the LP constraint O*(1-R) + I >= M degenerates to
    # O + I >= M (sound). The rearranged closed-form (T-M)/R is guarded in ratios.py.
    data = processed.optimization_df.copy()

    # Tier 5: target manpower plan mode. Replace Current Headcount with the user's target
    # for each family before any downstream column derivation. Existing families keep their
    # current count if no target is supplied; brand-new families injected by
    # process_workbook start at 0 and require the user to provide a target.
    if settings.optimization_mode == "target" and settings.target_headcounts:
        data["Current Headcount"] = data.apply(
            lambda row: int(settings.target_headcounts.get(row["Job Family"], row["Current Headcount"])),
            axis=1,
        )

    # Batch-2: when the active BU configuration supplies outsourceability or driver
    # overrides, re-derive the affected per-family columns BEFORE the downstream LP
    # math reads them. Empty overrides preserve the historical behavior.
    if settings.outsourceability_overrides:
        active_outsourceability = get_outsourceability_rules(settings.outsourceability_overrides)
        data["Outsourceability Type"] = data.apply(
            lambda row: active_outsourceability.get(row["Job Family"], row["Outsourceability Type"]),
            axis=1,
        )
    if settings.driver_overrides:
        mapped_workforce_df = pd.concat(
            [
                processed.inhouse_cleaned[["Activity_Standardized", "Profession_Standardized", "Job_Family"]]
                if not processed.inhouse_cleaned.empty
                else pd.DataFrame(columns=["Activity_Standardized", "Profession_Standardized", "Job_Family"]),
                processed.subcontractor_cleaned[["Activity_Standardized", "Profession_Standardized", "Job_Family"]]
                if not processed.subcontractor_cleaned.empty
                else pd.DataFrame(columns=["Activity_Standardized", "Profession_Standardized", "Job_Family"]),
            ],
            ignore_index=True,
        )
        recomputed_drivers = calculate_driver_values(
            mapped_workforce_df, driver_overrides=settings.driver_overrides
        )
        # Only families whose drivers were overridden get a refreshed Driver Value;
        # untouched families keep the value computed during process_workbook.
        for family in settings.driver_overrides:
            mask = data["Job Family"] == family
            if mask.any():
                data.loc[mask, "Driver Value"] = recomputed_drivers.get(family, pd.NA)

    data["Current Ratio"] = data.apply(
        lambda row: build_current_ratio_display(row["Current Headcount"], row["Driver Value"]),
        axis=1,
    )
    effective_max_ratios = get_maximum_ratio_rules(settings.max_ratio_overrides)
    data["Maximum Ratio"] = data["Job Family"].map(effective_max_ratios).fillna("N/A")
    data["Risk Factor"] = safe_numeric(settings.risk_factor)
    data = data.drop(columns=["Target Outsourced"], errors="ignore")

    # Build a lookup of user-defined families so per-family overrides apply during the
    # Minimum Headcount Needed and Outsourced v1 derivations.
    custom_by_name = custom_families_by_name(settings.custom_families or [])
    workbook_pairs_df = pd.concat(
        [
            processed.inhouse_cleaned[["Activity_Standardized", "Profession_Standardized"]]
            if not processed.inhouse_cleaned.empty
            else pd.DataFrame(columns=["Activity_Standardized", "Profession_Standardized"]),
            processed.subcontractor_cleaned[["Activity_Standardized", "Profession_Standardized"]]
            if not processed.subcontractor_cleaned.empty
            else pd.DataFrame(columns=["Activity_Standardized", "Profession_Standardized"]),
        ],
        ignore_index=True,
    )

    def _row_minimum(row):
        spec = custom_by_name.get(row["Job Family"])
        if spec is not None and spec.partial_config is not None and spec.outsourceability == "Partially Outsourceable":
            return calculate_partial_config_minimum(
                int(safe_numeric(row["Current Headcount"])),
                spec.partial_config,
                workbook_pairs_df,
            )
        return calculate_minimum_headcount_needed(
            row["Current Headcount"],
            row["Outsourceability Type"],
            row["Driver Value"],
            row["Maximum Ratio"],
            row.get("Current In-House Count", 0),
        )

    data["Minimum Headcount Needed"] = data.apply(_row_minimum, axis=1)
    data["Outsourced v1"] = data.apply(lambda row: calculate_outsourced_v1(row, settings.risk_factor), axis=1)
    data["In-house v1"] = data.apply(
        lambda row: max(0, int(safe_numeric(row["Current Headcount"])) - int(safe_numeric(row["Outsourced v1"]))),
        axis=1,
    )
    tenure_constraint_active = bool(
        settings.protect_tenured_inhouse
        and "Tenure Years" in processed.inhouse_cleaned.columns
        and processed.inhouse_cleaned["Tenure Years"].notna().any()
    )
    tenure_summary_columns = [
        "Tenured In-House Count",
        "Tenured Saudi In-House",
        "Tenured Non-Saudi In-House",
        "Tenured Saudi Cost Total",
        "Tenured Non-Saudi Cost Total",
        "Avg Cost Saudi Tenured Inhouse",
        "Avg Cost Non-Saudi Tenured Inhouse",
    ]
    data = data.drop(columns=[column for column in tenure_summary_columns if column in data.columns], errors="ignore")
    tenured_summary = (
        summarize_tenured_inhouse(processed.inhouse_cleaned, settings.tenure_threshold_years)
        if tenure_constraint_active
        else pd.DataFrame()
    )
    if not tenured_summary.empty:
        data = data.merge(tenured_summary, left_on="Job Family", right_index=True, how="left")
    for column in tenure_summary_columns:
        if column not in data.columns:
            data[column] = 0.0
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0.0)

    data = data.drop(columns=["Base Minimum In-House", "Effective Minimum In-House"], errors="ignore")
    data["Tenure Constraint Active"] = "Yes" if tenure_constraint_active else "No"
    data["Tenure Threshold (Years)"] = settings.tenure_threshold_years if tenure_constraint_active else pd.NA
    base_minimum_headcount_needed = data["Minimum Headcount Needed"].apply(
        lambda value: int(safe_numeric(value))
    )
    data["Minimum Headcount Needed"] = data.apply(
        lambda row: max(
            int(safe_numeric(row["Minimum Headcount Needed"])),
            int(safe_numeric(row["Tenured In-House Count"])) if tenure_constraint_active else 0,
        ),
        axis=1,
    )
    data["Tenure Driven Minimum"] = data.apply(
        lambda row: "Yes"
        if tenure_constraint_active
        and safe_numeric(row["Tenured In-House Count"]) > safe_numeric(base_minimum_headcount_needed.loc[row.name])
        else "No",
        axis=1,
    )
    data["Effective Avg Cost Saudi Inhouse"] = data.apply(
        lambda row: row["Avg Cost Saudi Tenured Inhouse"]
        if row["Tenure Driven Minimum"] == "Yes" and safe_numeric(row["Avg Cost Saudi Tenured Inhouse"]) > 0
        else row["Avg Cost Saudi Inhouse"],
        axis=1,
    )
    data["Effective Avg Cost Non-Saudi Inhouse"] = data.apply(
        lambda row: row["Avg Cost Non-Saudi Tenured Inhouse"]
        if row["Tenure Driven Minimum"] == "Yes" and safe_numeric(row["Avg Cost Non-Saudi Tenured Inhouse"]) > 0
        else row["Avg Cost Non-Saudi Inhouse"],
        axis=1,
    )
    data["In-House Cost Basis"] = data.apply(
        lambda row: "Tenured in-house average cost"
        if row["Tenure Driven Minimum"] == "Yes"
        else "Overall in-house average cost",
        axis=1,
    )
    # Soft-input override: re-split the in-house average cost into Saudi vs. non-Saudi using the
    # user-supplied premium. Default 1.10 reproduces historical behavior; the user can change it
    # to model "what if Saudis cost X% more / less" without re-uploading the workbook.
    data[
        ["Fully Loaded Cost per In-house Non-Saudi Employee", "Fully Loaded Cost per In-house Saudi Employee"]
    ] = data.apply(
        lambda row: calculate_inhouse_cost_split(
            row["Fully Loaded Cost per In-house Employee"],
            row["Current Total In-house Saudi"],
            row["Current In-House Non-Saudi Count"],
            saudi_premium=settings.saudi_cost_premium,
        ),
        axis=1,
    )

    if "Avg Cost Outsourced Original" in data.columns:
        data["Avg Cost Outsourced"] = data["Avg Cost Outsourced Original"]

    # Cost-inversion override (Scenario 1, safety officers): when the WORKBOOK has the
    # data inverted — in-house cheaper than outsourced — cap the base outsourced cost at
    # the in-house non-Saudi cost so the LP doesn't ignore the outsourceability rule on
    # cost grounds. We apply this to the BASE columns only, BEFORE the negotiated rate is
    # added, so that user-supplied insurance + service margin can still legitimately push
    # outsourced ABOVE in-house and signal "stop outsourcing" (Scenario 8).
    data["Avg Cost Outsourced"] = data.apply(
        lambda row: cap_outsourced_at_inhouse(
            row["Avg Cost Outsourced"],
            row["Fully Loaded Cost per In-house Non-Saudi Employee"],
        ),
        axis=1,
    )
    if "Avg Outsourced Base Cost Excluding Insurance Service" in data.columns:
        data["Avg Outsourced Base Cost Excluding Insurance Service"] = data.apply(
            lambda row: cap_outsourced_at_inhouse(
                row["Avg Outsourced Base Cost Excluding Insurance Service"],
                row["Fully Loaded Cost per In-house Non-Saudi Employee"],
            ) if pd.notna(row.get("Avg Outsourced Base Cost Excluding Insurance Service")) else pd.NA,
            axis=1,
        )

    # SYMMETRIC override (consultant's Scenario 1 feedback). Even after the cap above,
    # if outsourced and in-house non-Saudi costs are equal the LP's tie-break keeps
    # everyone in-house and the outsourceability rule is effectively ignored. Bump
    # in-house non-Saudi cost SLIGHTLY above outsourced for any Fully/Partially
    # outsourceable family so the LP strictly prefers to outsource up to the family's
    # ratio cap. Saudi in-house cost is intentionally left alone so saudization
    # compliance still works.
    data["Fully Loaded Cost per In-house Non-Saudi Employee"] = data.apply(
        lambda row: bump_inhouse_non_saudi_above_outsourced(
            row["Fully Loaded Cost per In-house Non-Saudi Employee"],
            row["Avg Cost Outsourced"],
            row.get("Outsourceability Type"),
        ),
        axis=1,
    )

    # Negotiated cost per outsourced FTE: BASE + user-supplied insurance + service margin.
    # When the workbook lacks per-family base data (the "Excluding" column is NA for that
    # family — typically when no subcontractor rows exist for it), fall back to the family's
    # average outsourced cost so insurance + margin STILL apply (Scenario 8 fix — previously
    # those families silently skipped the user's negotiated inputs).
    def _negotiated_cost(row):
        if not settings.negotiated_rates:
            return pd.NA
        excl = row.get("Avg Outsourced Base Cost Excluding Insurance Service")
        base = safe_numeric(excl) if pd.notna(excl) else safe_numeric(row["Avg Cost Outsourced"])
        return base + safe_numeric(settings.negotiated_insurance_cost) + safe_numeric(settings.negotiated_service_margin)
    data["Negotiated cost per outsourced FTE"] = data.apply(_negotiated_cost, axis=1)

    data[OUTSOURCED_UNIT_COST_BASIS_COLUMN] = data.apply(
        lambda row: safe_numeric(row["Negotiated cost per outsourced FTE"])
        if settings.negotiated_rates and pd.notna(row.get("Negotiated cost per outsourced FTE"))
        else safe_numeric(row["Avg Cost Outsourced"]),
        axis=1,
    )
    if settings.outsource_cost_discount is not None:
        # Soft-input override: replace the workbook-derived outsource cost with a fraction of
        # the in-house non-Saudi cost. E.g. discount=0.20 means "outsourcing is 20% cheaper
        # than non-Saudi in-house". Useful for what-if analysis when the workbook costs are
        # not believed to be representative of negotiated terms.
        discount = max(0.0, min(1.0, safe_numeric(settings.outsource_cost_discount)))
        data[OUTSOURCED_UNIT_COST_BASIS_COLUMN] = (
            (1.0 - discount) * data["Fully Loaded Cost per In-house Non-Saudi Employee"]
        )
    data[LEGACY_OUTSOURCED_COST_BASIS_COLUMN] = data[OUTSOURCED_UNIT_COST_BASIS_COLUMN]

    profession_saudization_rates = {
        normalize_lookup_text("Engineer"): settings.engineer_saudization_rate,
        normalize_lookup_text("Representative"): settings.sales_saudization_rate,
        normalize_lookup_text("Executive Management"): settings.executive_management_saudization_rate,
        normalize_lookup_text("Management"): settings.management_saudization_rate,
    }

    # Phase 3: high-performer protection. Count, per family, how many in-house
    # employees have Manpower Performance >= threshold, split by Saudi / Non-Saudi.
    # The LP uses these as per-classification lower bounds so the LP cannot
    # outsource a high performer or reclassify them. Current mode only.
    data["High Performer Saudi Floor"] = 0
    data["High Performer Non-Saudi Floor"] = 0
    if (
        settings.protect_high_performers
        and settings.optimization_mode != "target"
        and not processed.inhouse_cleaned.empty
        and "Manpower Performance" in processed.inhouse_cleaned.columns
    ):
        threshold = float(settings.high_performer_threshold)
        protected = processed.inhouse_cleaned[
            processed.inhouse_cleaned["Manpower Performance"] >= threshold
        ]
        if not protected.empty:
            saudi_counts = (
                protected[protected["Is_Saudi"] == 1]
                .groupby("Job_Family")
                .size()
                .to_dict()
            )
            non_saudi_counts = (
                protected[protected["Is_Saudi"] == 0]
                .groupby("Job_Family")
                .size()
                .to_dict()
            )
            data["High Performer Saudi Floor"] = data["Job Family"].map(
                lambda f: int(saudi_counts.get(f, 0))
            )
            data["High Performer Non-Saudi Floor"] = data["Job Family"].map(
                lambda f: int(non_saudi_counts.get(f, 0))
            )

    data, optimized_payroll, optimization_status = solve_optimization(
        data,
        enforce_saudization=settings.enforce_saudization,
        saudization_rate=settings.saudization_rate if settings.enforce_saudization else 0.0,
        can_reduce_current_saudi=settings.can_reduce_current_saudi,
        tenure_constraint_active=tenure_constraint_active,
        profession_saudization_rates=profession_saudization_rates,
        protect_current_saudi_percent=settings.protect_current_saudi_percent,
    )
    is_target_mode = settings.optimization_mode == "target"
    metadata = {
        OPTIMIZATION_STATUS_KEY: optimization_status,
        OPTIMIZED_PAYROLL_KEY: safe_numeric(optimized_payroll),
        "optimization_mode": settings.optimization_mode,
        "final_scenario_label": FINAL_SCENARIO_LABEL,
        "tenure_constraint_active": tenure_constraint_active,
        "risk_formula": "O * (1 - R) + I >= M",
    }
    if not is_target_mode:
        # Savings only make sense when there is a real "current" payroll baseline. In target
        # mode the user is sizing future headcount that does not yet exist, so a savings
        # delta would compare apples to oranges.
        current_payroll_cost = (
            data["Current Outsourced Count"] * data["Avg Cost Outsourced"]
            + data["Current In-House Count"] * data["Fully Loaded Cost per In-house Employee"]
        ).sum()
        metadata["current_payroll_cost"] = safe_numeric(current_payroll_cost)
        metadata[OPTIMIZED_SAVINGS_KEY] = safe_divide(
            current_payroll_cost - optimized_payroll, current_payroll_cost
        )
    else:
        metadata["target_headcount_total"] = int(safe_numeric(data["Current Headcount"].sum()))
    return data, metadata


def calculate_target_split_from_data(data: pd.DataFrame) -> pd.DataFrame:
    target_rows = []
    for _, row in data.iterrows():
        minimum_headcount_needed = int(safe_numeric(row["Minimum Headcount Needed"]))
        target_rows.append({
            "Job Family": row["Job Family"],
            "Outsourceability Type": row["Outsourceability Type"],
            "Driver Value": row["Driver Value"],
            "Current Headcount": int(row["Current Headcount"]),
            "Current Ratio": safe_divide(row["Driver Value"], row["Current Headcount"]),
            "Minimum Headcount Needed": int(safe_numeric(minimum_headcount_needed)),
        })
    return pd.DataFrame(target_rows)


def run_optimization(processed: ProcessedWorkbook, settings: OptimizationSettings) -> dict[str, Any]:
    data, metadata = prepare_model_data(processed, settings)
    optimized_results = build_optimized_results(
        data, metadata[OPTIMIZATION_STATUS_KEY], mode=settings.optimization_mode
    )
    audit_df = build_optimization_audit(data, metadata, settings)
    summary_data = build_summary_data(optimized_results, metadata, settings)
    # Client-facing export: just the Optimization Results + Summary sheets.
    # The Model Processing and Optimization Audit sheets are debug artifacts
    # the consultant doesn't need to hand off — kept out of the exported XLSX.
    export_bytes = build_results_workbook(
        optimized_results["results_df"],
        summary_data,
    )
    return {
        "data": data,
        "audit": audit_df,
        "metadata": metadata,
        "results": optimized_results,
        "summary_data": summary_data,
        "export_bytes": export_bytes,
    }


def build_summary_data(
    payroll_results: dict[str, Any],
    metadata: dict[str, Any],
    settings: OptimizationSettings,
) -> dict[str, list[object]]:
    summary_data = {
        "Metric": [
            "Total Cost (SAR / Month)",
            "Total Employees Headcount",
            "Saudi Labor",
            "In-House Non-Saudi Labor",
            "Outsourced Labor",
            "Saudization Rate Achieved (%)",
            "Optimization Status",
            "Outsourced Cost Type",
            "Can Reduce Saudi",
            "Saudization Enforced",
            "Risk Factor",
            "Tenure Constraint Active",
            "Tenure Threshold (Years)",
        ],
        "Value": [
            f"{payroll_results['total_cost']:,.0f}",
            payroll_results["total_employees_final"],
            payroll_results["total_saudi_final"],
            payroll_results["total_non_saudi_final"],
            payroll_results["total_outsourced_final"],
            f"{payroll_results['saudization_achieved']:.2f}",
            payroll_results["optimization_status"],
            FINAL_SCENARIO_LABEL,
            "Yes" if settings.can_reduce_current_saudi else "No",
            "Yes" if settings.enforce_saudization else "No",
            f"{settings.risk_factor:.2f}",
            "Yes" if metadata["tenure_constraint_active"] else "No",
            f"{settings.tenure_threshold_years:.1f}" if settings.protect_tenured_inhouse else "N/A",
        ],
    }
    if settings.enforce_saudization:
        summary_data["Metric"].insert(6, "Saudization Rate Required (%)")
        summary_data["Value"].insert(6, f"{settings.saudization_rate * 100:.2f}")
    return summary_data


def build_optimization_audit(
    data: pd.DataFrame,
    metadata: dict[str, Any],
    settings: OptimizationSettings,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    risk_factor = safe_numeric(settings.risk_factor)
    global_saudi_rate = safe_numeric(settings.saudization_rate) if settings.enforce_saudization else 0.0
    profession_rates = {
        normalize_lookup_text("Engineer"): settings.engineer_saudization_rate,
        normalize_lookup_text("Representative"): settings.sales_saudization_rate,
        normalize_lookup_text("Executive Management"): settings.executive_management_saudization_rate,
        normalize_lookup_text("Management"): settings.management_saudization_rate,
    }

    for _, row in data.iterrows():
        outsourced = int(safe_numeric(row.get(OUTSOURCED_COLUMN)))
        saudi = int(safe_numeric(row.get(IN_HOUSE_SAUDI_COLUMN)))
        non_saudi = int(safe_numeric(row.get(IN_HOUSE_NON_SAUDI_COLUMN)))
        inhouse = saudi + non_saudi
        total = int(safe_numeric(row.get("Current Headcount")))
        minimum = int(safe_numeric(row.get("Minimum Headcount Needed")))
        current_saudi = int(safe_numeric(row.get("Current Total In-house Saudi")))
        tenured_saudi = int(safe_numeric(row.get("Tenured Saudi In-House")))
        tenured_non_saudi = int(safe_numeric(row.get("Tenured Non-Saudi In-House")))
        effective_count = outsourced * (1 - risk_factor) + inhouse
        profession_rate = profession_rates.get(normalize_lookup_text(row.get("Job Family")))
        profession_required = (
            safe_numeric(profession_rate) * inhouse if profession_rate is not None else pd.NA
        )
        is_partially_outsourceable = row.get("Outsourceability Type") == "Partially Outsourceable"
        outsourced_v1_cap = int(safe_numeric(row.get("Outsourced v1")))
        outsourced_cost_basis = safe_numeric(
            row.get(
                OUTSOURCED_UNIT_COST_BASIS_COLUMN,
                row.get(LEGACY_OUTSOURCED_COST_BASIS_COLUMN),
            )
        )

        rows.append({
            "Job Family": row.get("Job Family"),
            "Outsourceability Type": row.get("Outsourceability Type"),
            "Current Headcount": total,
            "Final Outsourced": outsourced,
            "Final In-House": inhouse,
            "Final Saudi": saudi,
            "Final Non-Saudi": non_saudi,
            "Minimum Count": minimum,
            "Risk Factor": risk_factor,
            "Risk Formula": metadata.get("risk_formula", "O * (1 - R) + I >= M"),
            "Risk-Adjusted Effective Count": effective_count,
            "Risk-Adjusted Minimum Met": effective_count + 1e-9 >= minimum,
            "Strict In-House Minimum Met": inhouse >= minimum,
            "Outsourced v1 Cap": outsourced_v1_cap,
            "Outsource Cap Met": outsourced <= outsourced_v1_cap if is_partially_outsourceable else True,
            "Current Saudi Floor": current_saudi,
            "Saudi Floor Met": saudi >= current_saudi if not settings.can_reduce_current_saudi else True,
            "Tenured Saudi Floor": tenured_saudi if settings.protect_tenured_inhouse else 0,
            "Tenured Non-Saudi Floor": tenured_non_saudi if settings.protect_tenured_inhouse else 0,
            "Tenure Floor Met": (
                saudi >= tenured_saudi and non_saudi >= tenured_non_saudi
            ) if settings.protect_tenured_inhouse else True,
            "Profession Saudization Rate": profession_rate if profession_rate is not None else pd.NA,
            "Profession Saudi Required": profession_required,
            "Profession Saudization Met": saudi + 1e-9 >= profession_required if profession_rate is not None else True,
            "Outsourced Cost Basis": outsourced_cost_basis,
            "Global Saudization Required": global_saudi_rate,
        })

    return pd.DataFrame(rows)
