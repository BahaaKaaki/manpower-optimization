from __future__ import annotations

import re

import pandas as pd


def safe_numeric(value):
    if pd.isna(value):
        return 0.0
    try:
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def safe_divide(numerator, denominator):
    denominator = safe_numeric(denominator)
    if denominator == 0:
        return 0.0
    return safe_numeric(numerator) / denominator


def normalize_job_family(value):
    if pd.isna(value):
        return ""
    normalized = str(value).strip().lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def normalize_lookup_text(value):
    if pd.isna(value):
        return ""
    normalized = re.sub(r"\s+", " ", str(value).strip())
    return normalized.lower()


def is_blank(value):
    return pd.isna(value) or str(value).strip() == ""


def clean_lookup_text(value):
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).strip())


def get_numeric_from_row(row, candidates):
    normalized_columns = {
        normalize_lookup_text(column).replace("_", " "): column
        for column in row.index
    }
    compact_columns = {
        re.sub(r"[^a-z0-9]+", "", normalize_lookup_text(column)): column
        for column in row.index
    }
    for candidate in candidates:
        normalized_candidate = normalize_lookup_text(candidate).replace("_", " ")
        column = normalized_columns.get(normalized_candidate)
        if column is None:
            column = compact_columns.get(re.sub(r"[^a-z0-9]+", "", normalize_lookup_text(candidate)))
        if column is not None:
            value = safe_numeric(row.get(column))
            if value != 0:
                return value
    return 0.0


def detect_service_fee_column(columns):
    normalized_columns = {
        column: normalize_lookup_text(column).replace("_", " ")
        for column in columns
    }

    exact_candidates = [
        "service fee",
        "service fees",
        "service margin",
        "margin",
        "service charge",
    ]
    for candidate in exact_candidates:
        for column, normalized in normalized_columns.items():
            if normalized == candidate:
                return column

    for column, normalized in normalized_columns.items():
        if "service" in normalized and ("fee" in normalized or "margin" in normalized or "charge" in normalized):
            return column

    return None
