from __future__ import annotations

from typing import BinaryIO

import pandas as pd


REQUIRED_SHEETS = ["Inhouse", "Subcontractor"]

REQUIRED_INHOUSE_COLUMNS = [
    "No",
    "Location",
    "Profession",
    "Nationality",
    "Total Paid",
    "Total Unpaid",
]

REQUIRED_SUBCONTRACTOR_COLUMNS = [
    "No",
    "Working in",
    "Profession",
    "Nationality",
    "Basic",
]


class WorkbookValidationError(ValueError):
    pass


def read_manpower_workbook(excel_source: str | BinaryIO) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read the required manpower workbook sheets and normalize column names."""
    try:
        xlsx = pd.ExcelFile(excel_source)
    except Exception as exc:
        raise WorkbookValidationError(
            "Could not read the uploaded file. Please ensure it is a valid .xlsx Excel workbook."
        ) from exc

    available_sheets = xlsx.sheet_names
    missing_sheets = [s for s in REQUIRED_SHEETS if s not in available_sheets]
    if missing_sheets:
        raise WorkbookValidationError(
            f"Missing required sheet(s): {', '.join(missing_sheets)}. "
            f"The workbook must contain both an 'Inhouse' and a 'Subcontractor' sheet. "
            f"Found sheets: {', '.join(available_sheets)}."
        )

    inhouse_df = pd.read_excel(xlsx, sheet_name="Inhouse")
    subcontractor_df = pd.read_excel(xlsx, sheet_name="Subcontractor")

    inhouse_df.columns = inhouse_df.columns.str.strip()
    subcontractor_df.columns = subcontractor_df.columns.str.strip()

    _validate_columns(inhouse_df, REQUIRED_INHOUSE_COLUMNS, "Inhouse")
    _validate_columns(subcontractor_df, REQUIRED_SUBCONTRACTOR_COLUMNS, "Subcontractor")

    if inhouse_df.empty and subcontractor_df.empty:
        raise WorkbookValidationError(
            "Both sheets are empty. The workbook must contain employee data in at least one sheet."
        )

    return inhouse_df, subcontractor_df


def _validate_columns(df: pd.DataFrame, required: list[str], sheet_name: str) -> None:
    available = set(df.columns)
    missing = [col for col in required if col not in available]
    if missing:
        raise WorkbookValidationError(
            f"The '{sheet_name}' sheet is missing required column(s): {', '.join(missing)}. "
            f"Please check that the workbook follows the expected template format."
        )
