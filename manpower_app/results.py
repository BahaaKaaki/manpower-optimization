from __future__ import annotations

import pandas as pd

from manpower_app.optimization import (
    IN_HOUSE_NON_SAUDI_COLUMN,
    IN_HOUSE_SAUDI_COLUMN,
    OUTSOURCED_COLUMN,
)
from manpower_app.terminology import (
    LEGACY_OUTSOURCED_COST_BASIS_COLUMN,
    OUTSOURCED_UNIT_COST_BASIS_COLUMN,
)
from manpower_app.utils import safe_divide, safe_numeric


def build_optimized_results(data, optimization_status, mode: str = "current"):
    results_data = []
    for _, row in data.iterrows():
        saudi = int(safe_numeric(row[IN_HOUSE_SAUDI_COLUMN]))
        non_saudi = int(safe_numeric(row[IN_HOUSE_NON_SAUDI_COLUMN]))
        outsourced = int(safe_numeric(row[OUTSOURCED_COLUMN]))

        cost_saudi = safe_numeric(row['Fully Loaded Cost per In-house Saudi Employee']) * saudi
        cost_non_saudi = safe_numeric(row['Fully Loaded Cost per In-house Non-Saudi Employee']) * non_saudi
        cost_basis = safe_numeric(
            row.get(
                OUTSOURCED_UNIT_COST_BASIS_COLUMN,
                row.get(LEGACY_OUTSOURCED_COST_BASIS_COLUMN),
            )
        )
        cost_outsourced = cost_basis * outsourced

        results_data.append({
            'Job Family': row['Job Family'],
            'Saudi Labor': saudi,
            'In-House Non-Saudi Labor': non_saudi,
            'Outsourced Labor': outsourced,
            'Total Employees Headcount': saudi + non_saudi + outsourced,
            'Cost - Saudi Labor (SAR)': cost_saudi,
            'Cost - In-House Non-Saudi Labor (SAR)': cost_non_saudi,
            'Cost - Outsourced Labor (SAR)': cost_outsourced,
            'Total Cost (SAR)': cost_saudi + cost_non_saudi + cost_outsourced,
        })

    results_df = pd.DataFrame(results_data)
    total_saudi_final = int(results_df['Saudi Labor'].sum()) if not results_df.empty else 0
    total_non_saudi_final = int(results_df['In-House Non-Saudi Labor'].sum()) if not results_df.empty else 0
    total_outsourced_final = int(results_df['Outsourced Labor'].sum()) if not results_df.empty else 0
    total_employees_final = total_saudi_final + total_non_saudi_final + total_outsourced_final
    total_inhouse_final = total_saudi_final + total_non_saudi_final
    saudization_achieved = safe_divide(total_saudi_final, total_inhouse_final) * 100

    return {
        'results_df': results_df,
        'total_cost': safe_numeric(results_df['Total Cost (SAR)'].sum()) if not results_df.empty else 0.0,
        'total_saudi_final': total_saudi_final,
        'total_non_saudi_final': total_non_saudi_final,
        'total_outsourced_final': total_outsourced_final,
        'total_employees_final': total_employees_final,
        'saudization_achieved': saudization_achieved,
        'optimization_status': optimization_status,
        'optimization_mode': mode,
        'total_cost_saudi': safe_numeric(results_df['Cost - Saudi Labor (SAR)'].sum()) if not results_df.empty else 0.0,
        'total_cost_non_saudi': safe_numeric(results_df['Cost - In-House Non-Saudi Labor (SAR)'].sum()) if not results_df.empty else 0.0,
        'total_cost_outsourced': safe_numeric(results_df['Cost - Outsourced Labor (SAR)'].sum()) if not results_df.empty else 0.0,
    }
