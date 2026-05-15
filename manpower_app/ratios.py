from __future__ import annotations

import math
from difflib import get_close_matches
from pathlib import Path

import pandas as pd

from manpower_app.config import RATIO_FILE_PATH
from manpower_app.utils import safe_divide, safe_numeric, normalize_job_family


def resolve_average_costs(avg_cost_saudi, avg_cost_non_saudi, avg_cost_outsourced):
    avg_cost_saudi = safe_numeric(avg_cost_saudi)
    avg_cost_non_saudi = safe_numeric(avg_cost_non_saudi)
    avg_cost_outsourced = safe_numeric(avg_cost_outsourced)

    for _ in range(3):
        if avg_cost_outsourced == 0:
            if avg_cost_saudi > 0:
                avg_cost_outsourced = 0.6 * avg_cost_saudi
            elif avg_cost_non_saudi > 0:
                avg_cost_outsourced = 0.8 * avg_cost_non_saudi

        if avg_cost_non_saudi == 0:
            if avg_cost_saudi > 0:
                avg_cost_non_saudi = 0.8 * avg_cost_saudi
            elif avg_cost_outsourced > 0:
                avg_cost_non_saudi = 1.2 * avg_cost_outsourced

        if avg_cost_saudi == 0:
            if avg_cost_outsourced > 0:
                avg_cost_saudi = 1.5 * avg_cost_outsourced
            elif avg_cost_non_saudi > 0:
                avg_cost_saudi = 1.25 * avg_cost_non_saudi

    return pd.Series(
        [avg_cost_saudi, avg_cost_non_saudi, avg_cost_outsourced],
        index=["Avg Cost Saudi Inhouse", "Avg Cost Non-Saudi Inhouse", "Avg Cost Outsourced"],
    )


def lookup_ratio_rule(job_family, ratio_rules, cutoff=0.8):
    job_family_key = normalize_job_family(job_family)
    exact_rule = ratio_rules.get(job_family_key)
    if exact_rule:
        return exact_rule, "exact", job_family_key

    candidates = get_close_matches(job_family_key, ratio_rules.keys(), n=1, cutoff=cutoff)
    if candidates:
        matched_key = candidates[0]
        return ratio_rules.get(matched_key, {}), "fuzzy", matched_key

    return {}, "none", ""


def format_ratio_denominator(value):
    numeric_value = safe_numeric(value)
    if numeric_value <= 0:
        return "N/A"
    if float(numeric_value).is_integer():
        return f"{int(numeric_value):,}"
    return f"{numeric_value:,.1f}"


def build_current_ratio_display(total_headcount, driver_value):
    total_headcount = int(safe_numeric(total_headcount))
    if total_headcount <= 0 or pd.isna(driver_value):
        return "N/A"

    denominator = safe_divide(driver_value, total_headcount)
    return f"1:{int(math.floor(denominator + 0.5))}"


def parse_ratio_denominator(ratio_text):
    if pd.isna(ratio_text):
        return pd.NA

    parts = str(ratio_text).split(":", 1)
    if len(parts) != 2:
        return pd.NA

    try:
        return float(parts[1].replace(",", "").strip())
    except ValueError:
        return pd.NA


def calculate_minimum_headcount_needed(total_headcount, outsourceability_type, driver_value, maximum_ratio, current_inhouse_count=0):
    total_headcount = int(safe_numeric(total_headcount))
    current_inhouse_count = int(safe_numeric(current_inhouse_count))
    if total_headcount <= 0:
        return 0

    if outsourceability_type == "Fully Outsourceable":
        return 0

    if outsourceability_type == "Not Outsourceable":
        return total_headcount

    if pd.isna(driver_value):
        return min(total_headcount, current_inhouse_count)

    ratio_denominator = parse_ratio_denominator(maximum_ratio)
    if pd.isna(ratio_denominator) or safe_numeric(ratio_denominator) <= 0:
        return min(total_headcount, current_inhouse_count)

    minimum_headcount_needed = max(0, math.ceil(safe_numeric(driver_value) / safe_numeric(ratio_denominator)))
    return min(total_headcount, minimum_headcount_needed)


def round_headcount(value):
    return int(math.floor(safe_numeric(value) + 0.5))


def calculate_partial_config_minimum(
    total_headcount: int,
    partial_config,
    workbook_pairs_df: pd.DataFrame,
) -> int:
    """Minimum in-house count derived from a user-defined partial_config.

    ``partial_config`` is a :class:`manpower_app.family_specs.PartialConfig` (or ``None``).
    For driver-based configs, the driver count is the number of rows in
    ``workbook_pairs_df`` whose ``Activity_Standardized`` + ``Profession_Standardized``
    match the configured driver. The frame should be the combined inhouse + subcontractor
    standardized pair data.

    Returns ``0`` for ``None``, percent=0, or otherwise unresolvable configs — meaning
    no minimum is enforced beyond zero. The caller's other constraints (Saudi floor, etc.)
    still apply.
    """
    total_headcount = int(safe_numeric(total_headcount))
    if total_headcount <= 0 or partial_config is None:
        return 0

    kind = getattr(partial_config, "kind", None)
    if kind == "percent":
        percent = safe_numeric(getattr(partial_config, "percent", 0))
        return max(0, math.ceil(total_headcount * (1.0 - percent)))
    if kind == "fixed":
        fixed_count = int(safe_numeric(getattr(partial_config, "fixed_count", 0)))
        return min(total_headcount, max(0, fixed_count))
    if kind == "driver":
        denom = parse_ratio_denominator(getattr(partial_config, "max_ratio", None))
        if pd.isna(denom) or safe_numeric(denom) <= 0:
            return 0
        if workbook_pairs_df is None or workbook_pairs_df.empty:
            return 0
        driver_count = int(
            (
                (workbook_pairs_df["Activity_Standardized"] == getattr(partial_config, "driver_activity", None))
                & (workbook_pairs_df["Profession_Standardized"] == getattr(partial_config, "driver_profession", None))
            ).sum()
        )
        return min(total_headcount, max(0, math.ceil(driver_count / safe_numeric(denom))))
    return 0


def calculate_outsourced_v1(row, risk_factor):
    total_headcount = int(safe_numeric(row.get("Current Headcount")))
    outsourceability_type = row.get("Outsourceability Type")

    if total_headcount <= 0:
        return 0
    if outsourceability_type == "Fully Outsourceable":
        return total_headcount
    if outsourceability_type == "Not Outsourceable":
        return 0
    if pd.isna(row.get("Driver Value")):
        return min(total_headcount, int(safe_numeric(row.get("Current Outsourced Count"))))

    risk_factor = safe_numeric(risk_factor)
    if risk_factor == 0:
        return total_headcount

    outsourceable_headcount = total_headcount - safe_numeric(row.get("Minimum Headcount Needed"))
    outsourced_v1 = round_headcount(outsourceable_headcount / risk_factor)
    return min(total_headcount, max(0, outsourced_v1))


def calculate_driver_values(mapped_workforce_df):
    def count_rows(activity=None, professions=None, job_family=None, job_families=None):
        df = mapped_workforce_df
        if activity is not None:
            df = df[df["Activity_Standardized"] == activity]
        if professions is not None:
            df = df[df["Profession_Standardized"].isin(professions)]
        if job_family is not None:
            df = df[df["Job_Family"] == job_family]
        if job_families is not None:
            df = df[df["Job_Family"].isin(job_families)]
        return int(len(df))

    driver_values = {
        "Quarries Foreman": count_rows(
            activity="Quarries",
            job_families=["Labor", "Skilled Labor", "Technician"],
        ),
        "Safety Officer": int(
            len(
                mapped_workforce_df[
                    mapped_workforce_df["Activity_Standardized"].isin(
                        ["Factory", "Idle Saudi Labor", "Installation", "Quarries"]
                    )
                ]
            )
        ),
        "Production Foreman": count_rows(
            activity="Factory",
            job_families=["Labor", "Skilled Labor", "Technician"],
        ),
        "Installation Foreman": count_rows(
            activity="Installation",
            job_families=["Skilled Labor", "Labor"],
        ),
        "Showroom Supervisor": count_rows(
            activity="Showroom",
            professions=["Labor", "Skilled Labor", "Store Keeper", "Foreman", "Operator"],
        ),
    }

    driver_values["Quarries Supervisor"] = count_rows(
        activity="Quarries", job_family="Quarries Foreman"
    )
    driver_values["Installation Supervisor"] = count_rows(
        activity="Installation", job_family="Installation Foreman"
    )
    driver_values["Factory Supervisor"] = count_rows(
        activity="Factory", job_family="Production Foreman"
    )

    return driver_values


def load_ratio_rules(excel_source=None):
    source = excel_source if excel_source is not None else RATIO_FILE_PATH

    if isinstance(source, (str, Path)) and not Path(source).exists():
        return pd.DataFrame()

    try:
        ratio_df = pd.read_excel(source, sheet_name=0, header=1)
    except Exception:
        return pd.DataFrame()

    ratio_df = ratio_df.rename(
        columns={
            "Unique List of Job Families": "Job Family",
            "Outsourceability": "Outsourceability Type",
            "Total Count": "Ratio File Total Count",
            "Current Outsourced Ratio": "Current Outsourced Ratio",
            "Driver": "Driver Description",
            "Maximum Ratio Based on Research": "Maximum Ratio",
        }
    )

    required_cols = ["Job Family", "Outsourceability Type"]
    if not all(col in ratio_df.columns for col in required_cols):
        return pd.DataFrame()

    ratio_df = ratio_df[ratio_df["Job Family"].notna()].copy()
    ratio_df["Job Family"] = ratio_df["Job Family"].astype(str).str.strip()
    ratio_df["Job Family Key"] = ratio_df["Job Family"].apply(normalize_job_family)
    ratio_df["Outsourceability Type"] = (
        ratio_df["Outsourceability Type"]
        .astype(str)
        .str.strip()
        .replace(
            {
                "No": "Not Outsourceable",
                "Yes": "Fully Outsourceable",
                "Partial": "Partially Outsourceable",
                "Partially": "Partially Outsourceable",
            }
        )
    )

    for col in ["Ratio File Total Count", "Current Outsourced Ratio", "Maximum Ratio"]:
        if col in ratio_df.columns:
            ratio_df[col] = pd.to_numeric(ratio_df[col], errors="coerce")
        else:
            ratio_df[col] = pd.NA

    if "Driver Description" not in ratio_df.columns:
        ratio_df["Driver Description"] = ""

    ratio_df["Driver Description"] = ratio_df["Driver Description"].fillna("").astype(str).str.strip()
    ratio_df["Driver Value"] = pd.to_numeric(ratio_df["Driver Description"], errors="coerce")

    return ratio_df[
        [
            "Job Family",
            "Job Family Key",
            "Outsourceability Type",
            "Driver Description",
            "Driver Value",
            "Maximum Ratio",
            "Current Outsourced Ratio",
            "Ratio File Total Count",
        ]
    ].drop_duplicates(subset=["Job Family"], keep="first")
