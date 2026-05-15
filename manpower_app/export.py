from __future__ import annotations

import io

import pandas as pd


def build_results_workbook(
    results_df: pd.DataFrame,
    summary_data: dict[str, list[object]],
    processing_debug_df: pd.DataFrame | None = None,
    audit_df: pd.DataFrame | None = None,
) -> bytes:
    """Build the Excel workbook returned by the Streamlit download button."""
    output_buffer = io.BytesIO()
    with pd.ExcelWriter(output_buffer, engine="openpyxl") as writer:
        results_df.to_excel(writer, sheet_name="Optimization Results", index=False)
        if audit_df is not None:
            audit_df.to_excel(writer, sheet_name="Optimization Audit", index=False)
        if processing_debug_df is not None:
            processing_debug_df.to_excel(writer, sheet_name="Model Processing", index=False)
        pd.DataFrame(summary_data).to_excel(writer, sheet_name="Summary", index=False)

    output_buffer.seek(0)
    return output_buffer.getvalue()
