from __future__ import annotations

import functools
import re

import pandas as pd

_WHITESPACE_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


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
    return _WHITESPACE_RE.sub(" ", normalized)


@functools.lru_cache(maxsize=4096)
def _normalize_lookup_text_str(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", value.strip()).lower()


def normalize_lookup_text(value):
    # ``normalize_lookup_text`` is on the hot path of every row-wise cost
    # calculation. The set of distinct inputs is tiny (column names + a few
    # constants), but it gets called millions of times during upload, so we
    # cache the string-only fast path via _normalize_lookup_text_str.
    if pd.isna(value):
        return ""
    if isinstance(value, str):
        return _normalize_lookup_text_str(value)
    return _normalize_lookup_text_str(str(value))


def is_blank(value):
    return pd.isna(value) or str(value).strip() == ""


def clean_lookup_text(value):
    if pd.isna(value):
        return ""
    return _WHITESPACE_RE.sub(" ", str(value).strip())


@functools.lru_cache(maxsize=32)
def _build_row_column_resolvers(columns: tuple[str, ...]):
    """Compute the (normalized, compact) column-name lookup dicts for a row index.

    Cached on the column tuple so successive rows of the same DataFrame share
    one allocation — the original per-row dict comprehensions accounted for
    ~22s out of a 94s upload on Manpower.xlsx.
    """
    normalized = {
        normalize_lookup_text(column).replace("_", " "): column
        for column in columns
    }
    compact = {
        _NON_ALNUM_RE.sub("", normalize_lookup_text(column)): column
        for column in columns
    }
    return normalized, compact


def get_numeric_from_row(row, candidates):
    normalized_columns, compact_columns = _build_row_column_resolvers(tuple(row.index))
    for candidate in candidates:
        normalized_candidate = normalize_lookup_text(candidate).replace("_", " ")
        column = normalized_columns.get(normalized_candidate)
        if column is None:
            column = compact_columns.get(_NON_ALNUM_RE.sub("", normalize_lookup_text(candidate)))
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
