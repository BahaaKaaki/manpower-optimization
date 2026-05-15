from __future__ import annotations

import pandas as pd

from manpower_app.utils import normalize_lookup_text, safe_numeric


def detect_tenure_column(columns):
    normalized_columns = {
        column: normalize_lookup_text(column).replace("_", " ")
        for column in columns
    }

    numeric_candidates = [
        "tenure",
        "tenure years",
        "years of service",
        "service years",
        "years in service",
        "seniority",
    ]
    date_candidates = [
        "hire date",
        "hiring date",
        "joining date",
        "join date",
        "date of joining",
        "employment date",
        "start date",
        "doj",
    ]

    for candidate in numeric_candidates:
        for column, normalized in normalized_columns.items():
            if normalized == candidate:
                return column, "numeric"

    for candidate in date_candidates:
        for column, normalized in normalized_columns.items():
            if normalized == candidate:
                return column, "date"

    for column, normalized in normalized_columns.items():
        if "tenure" in normalized or "seniority" in normalized:
            return column, "numeric"
        if "service" in normalized and "year" in normalized:
            return column, "numeric"
        if (
            "date" in normalized
            and any(token in normalized for token in ["join", "hire", "start", "employment"])
        ) or normalized == "doj":
            return column, "date"

    return None, None


def derive_tenure_years(values, mode, as_of_date=None):
    if as_of_date is None:
        as_of_date = pd.Timestamp.today().normalize()

    if mode == "numeric":
        return pd.to_numeric(values, errors="coerce")

    if mode == "date":
        parsed_dates = pd.to_datetime(values, errors="coerce")
        numeric_values = pd.to_numeric(values, errors="coerce")
        excel_serial_dates = numeric_values.between(20000, 60000)
        if excel_serial_dates.any():
            parsed_dates = parsed_dates.copy()
            parsed_dates.loc[excel_serial_dates] = pd.to_datetime(
                numeric_values.loc[excel_serial_dates],
                unit="D",
                origin="1899-12-30",
                errors="coerce",
            )
        tenure_days = (as_of_date - parsed_dates).dt.days
        return tenure_days / 365.25

    return pd.Series(index=values.index, dtype="float64")


def summarize_tenured_inhouse(inhouse_df, tenure_threshold):
    summary_columns = [
        "Tenured In-House Count",
        "Tenured Saudi In-House",
        "Tenured Non-Saudi In-House",
        "Tenured Saudi Cost Total",
        "Tenured Non-Saudi Cost Total",
        "Avg Cost Saudi Tenured Inhouse",
        "Avg Cost Non-Saudi Tenured Inhouse",
    ]

    if "Tenure Years" not in inhouse_df.columns:
        return pd.DataFrame(columns=summary_columns)

    eligible_df = inhouse_df[
        inhouse_df["Tenure Years"].notna() & (inhouse_df["Tenure Years"] >= safe_numeric(tenure_threshold))
    ].copy()
    if eligible_df.empty:
        return pd.DataFrame(columns=summary_columns)

    summary = eligible_df.groupby("Job_Family").agg({
        "No": "count",
        "Is_Saudi": "sum",
        "Saudi_Cost_Per_Employee": "sum",
        "Non_Saudi_Cost_Per_Employee": "sum",
    }).rename(columns={
        "No": "Tenured In-House Count",
        "Is_Saudi": "Tenured Saudi In-House",
        "Saudi_Cost_Per_Employee": "Tenured Saudi Cost Total",
        "Non_Saudi_Cost_Per_Employee": "Tenured Non-Saudi Cost Total",
    })

    summary["Tenured Non-Saudi In-House"] = (
        summary["Tenured In-House Count"] - summary["Tenured Saudi In-House"]
    )
    summary["Avg Cost Saudi Tenured Inhouse"] = summary.apply(
        lambda row: row["Tenured Saudi Cost Total"] / row["Tenured Saudi In-House"]
        if row["Tenured Saudi In-House"] > 0 else 0,
        axis=1,
    )
    summary["Avg Cost Non-Saudi Tenured Inhouse"] = summary.apply(
        lambda row: row["Tenured Non-Saudi Cost Total"] / row["Tenured Non-Saudi In-House"]
        if row["Tenured Non-Saudi In-House"] > 0 else 0,
        axis=1,
    )

    return summary[summary_columns]
