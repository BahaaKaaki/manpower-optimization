from __future__ import annotations


OUTSOURCEABILITY_RULES = {
    'Idle Saudi Skilled Labor': 'Not Outsourceable',
    'Quarries Foreman': 'Partially Outsourceable',
    'Safety Officer': 'Partially Outsourceable',
    'Security Guard': 'Fully Outsourceable',
    'Quarries Supervisor': 'Partially Outsourceable',
    'Coordinator': 'Not Outsourceable',
    'Clerk': 'Partially Outsourceable',
    'Installation Supervisor': 'Partially Outsourceable',
    'Representative': 'Not Outsourceable',
    'Production Foreman': 'Partially Outsourceable',
    'Administration': 'Not Outsourceable',
    'Management': 'Not Outsourceable',
    'Engineer': 'Not Outsourceable',
    'Surveyor': 'Not Outsourceable',
    'Factory Supervisor': 'Partially Outsourceable',
    'Installation Foreman': 'Partially Outsourceable',
    'Assistant': 'Not Outsourceable',
    'Draftsman': 'Not Outsourceable',
    'Installation Operator': 'Fully Outsourceable',
    'Controller': 'Partially Outsourceable',
    'Skilled Labor': 'Fully Outsourceable',
    'Labor': 'Fully Outsourceable',
    'Technician': 'Fully Outsourceable',
    'Factory Operator': 'Fully Outsourceable',
    'Installation Finisher': 'Fully Outsourceable',
    'Driver': 'Fully Outsourceable',
    'Factory Inspector': 'Not Outsourceable',
    'Factory Finisher': 'Fully Outsourceable',
    'Installation Technical Operator': 'Fully Outsourceable',
    'Time Keeper': 'Fully Outsourceable',
    'Quarries Operator': 'Fully Outsourceable',
    'Store Keeper': 'Fully Outsourceable',
    'Executive Management': 'Not Outsourceable',
    'Showroom Supervisor': 'Partially Outsourceable',
    'Geologist': 'Not Outsourceable',
    'Analyst': 'Not Outsourceable',
    'Factory Technical Operator': 'Fully Outsourceable',
    'Installation Inspector': 'Not Outsourceable',
    'Quarries Technical Operator': 'Fully Outsourceable',
}

MAXIMUM_RATIO_RULES = {
    'Quarries Foreman': '1:15',
    'Safety Officer': '1:50',
    'Quarries Supervisor': '1:10',
    'Installation Supervisor': '1:12',
    'Production Foreman': '1:15',
    'Factory Supervisor': '1:10',
    'Installation Foreman': '1:40',
    'Showroom Supervisor': '1:10',
}


# Job families whose in-house headcount is anchored to the current Head Office count.
# For these families the LP is capped so that all Head Office staff stay in-house and only
# the non-HQ portion can be outsourced. If the projected total drops below the HQ count,
# the family is fully in-house. See manpower_app.optimization._max_outsourced_allowed.
HQ_FIXED_INHOUSE_FAMILIES = frozenset({"Clerk", "Controller"})


_OUTSOURCEABILITY_VALUES = frozenset(
    {"Fully Outsourceable", "Partially Outsourceable", "Not Outsourceable"}
)


def get_outsourceability_rules(overrides=None):
    """Return the active outsourceability map, merging optional BU overrides over the
    hardcoded defaults. Per Saad's batch-2 spec each Business Unit can override the
    classification per family; an `overrides=None` call reproduces the legacy behavior.

    Unknown families and invalid values in `overrides` are silently dropped so a stale
    BU configuration cannot corrupt the in-process rule set."""
    if not overrides:
        return dict(OUTSOURCEABILITY_RULES)
    merged = dict(OUTSOURCEABILITY_RULES)
    for family, value in overrides.items():
        if family in OUTSOURCEABILITY_RULES and value in _OUTSOURCEABILITY_VALUES:
            merged[family] = value
    return merged


def get_maximum_ratio_rules(overrides=None):
    """Return the active max-ratio map, merging optional BU overrides. Overrides keep
    the existing 'N:M' string shape so downstream parsing in ratios.py is unchanged."""
    if not overrides:
        return dict(MAXIMUM_RATIO_RULES)
    merged = dict(MAXIMUM_RATIO_RULES)
    for family, value in overrides.items():
        if family in MAXIMUM_RATIO_RULES and isinstance(value, str) and ":" in value:
            merged[family] = value
    return merged
