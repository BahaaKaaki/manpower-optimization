from __future__ import annotations

import pandas as pd

from manpower_app.utils import get_numeric_from_row, normalize_lookup_text, safe_numeric


def get_insurance_cost(sponsor):
    sponsor = normalize_lookup_text(sponsor)
    if sponsor in ["ewan", "mahara", "tatweer"]:
        return 38
    if sponsor == "saed azka":
        return 46
    if sponsor == "arco":
        return 50
    return 38


def calculate_outsource_employee_cost(row, service_fee_column=None, negotiated_service_margin=False):
    cost = calculate_outsource_base_employee_cost(row)

    insurance_cost = get_numeric_from_row(
        row,
        ["Insurance Costs", "Insurance Cost", "Medical Insurance Cost"],
    )
    cost += insurance_cost if insurance_cost > 0 else get_insurance_cost(row.get("Sponser"))

    service_margin = safe_numeric(row.get(service_fee_column)) if service_fee_column else get_numeric_from_row(
        row,
        ["Service Margin", "Service Fee", "Service Fees", "Service Charge"],
    )
    # The `negotiated_service_margin` flag historically capped the workbook's per-row
    # margin at 500 SAR (the assumed "negotiated floor"). That floor is now the user's
    # responsibility via the settings.negotiated_service_margin input on the LP path,
    # so the flag is kept for the call-site signature but no longer mutates the cost.
    cost += service_margin

    return cost


def calculate_outsource_base_employee_cost(row):
    return sum(
        get_numeric_from_row(row, [column])
        for column in [
            "Basic",
            "Housing Paid",
            "Trans Paid",
            "Food",
            "Gosi",
            "Value O.T (SAR)",
            "Government Fees",
            "E.O.S monthly",
        ]
    )


def calculate_inhouse_fully_loaded_employee_cost(row):
    cost = sum(
        get_numeric_from_row(row, candidates)
        for candidates in [
            ["Value O.T (SAR)", "Value O.T", "O.T Value"],
            ["Basic"],
            ["Housing Paid"],
            ["Housing Unpaid"],
            ["Tickt Paid"],
            ["Tickt Unpaid"],
            ["Trans Paid", "Trans. Paid"],
            ["Trans.Unpaid", "Trans. Unpaid"],
            ["Medical Paid"],
            ["Med.Unpaid", "Med. Unpaid"],
            ["Vac. Paid"],
            ["Vac. Unpaid"],
            ["EOS Paid"],
            ["EOS Unpaid"],
            ["CO Social"],
            ["Food Paid"],
            ["Food Unpaid"],
            ["Iqama"],
            ["Paid Before"],
            ["Bonus"],
            ["Other Paid"],
            ["Other Accrude", "Other Accrued"],
            ["Te. Accrued", "Tel. Accrued"],
            ["Tel.Paid", "Tel. Paid"],
        ]
    )

    return cost


DEFAULT_SAUDI_COST_PREMIUM = 1.10


def cap_outsourced_at_inhouse(outsourced_unit_cost, inhouse_non_saudi_unit_cost):
    """Enforce the consultant assumption that outsourced workers are not more expensive
    than in-house non-Saudis. If the uploaded workbook has the inversion (e.g. safety
    officers where in-house is cheaper than outsourced), the LP would otherwise prefer
    in-house on cost grounds and ignore the outsourceability rule. Capping outsourced
    at the in-house non-Saudi unit cost neutralizes the cost inversion and lets the
    ratio/outsourceability rule decide. Mirrors the Saudi premium clamp pattern below.
    """
    outsourced = safe_numeric(outsourced_unit_cost)
    inhouse = safe_numeric(inhouse_non_saudi_unit_cost)
    if inhouse <= 0 or outsourced <= 0:
        return outsourced
    return min(outsourced, inhouse)


def calculate_inhouse_cost_split(average_cost, saudi_count, non_saudi_count, saudi_premium=DEFAULT_SAUDI_COST_PREMIUM):
    """Split a blended in-house average cost into per-Saudi and per-non-Saudi costs.

    ``saudi_premium`` is the assumed multiplier of Saudi cost over non-Saudi cost (1.10 by
    default — Saudis cost 10% more). The user can override it via the soft-input settings
    to model "what if Saudis cost X% more". The premium is floored at ``1.0`` so Saudis
    can never be cheaper than non-Saudis within a job family — if the inputs would
    produce that inversion, we fall back to 1.0 × non-Saudi.
    """
    average_cost = safe_numeric(average_cost)
    saudi_count = safe_numeric(saudi_count)
    non_saudi_count = safe_numeric(non_saudi_count)
    premium = safe_numeric(saudi_premium) or DEFAULT_SAUDI_COST_PREMIUM
    premium = max(1.0, premium)

    if saudi_count + non_saudi_count == 0:
        non_saudi_cost = average_cost * 2 / (1 + premium)
    else:
        non_saudi_cost = (
            average_cost * (saudi_count + non_saudi_count)
            / (non_saudi_count + premium * saudi_count)
        )

    return pd.Series(
        [non_saudi_cost, premium * non_saudi_cost],
        index=[
            "Fully Loaded Cost per In-house Non-Saudi Employee",
            "Fully Loaded Cost per In-house Saudi Employee",
        ],
    )
