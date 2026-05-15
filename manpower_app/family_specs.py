"""User-defined job family specifications.

These dataclasses describe how the user customizes the optimizer at runtime — which
(activity, profession) pairs map to a custom job family, how that family is treated
for outsourceability, and (for brand-new families with no payroll rows) what unit
costs the LP should use.

The models are deliberately placed here (in :mod:`manpower_app`) rather than in
:mod:`manpower_api` so the optimization pipeline can use them without depending on
FastAPI / pydantic. The API layer wraps them with pydantic for request validation
and converts to these dataclasses before invoking the service layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Literal


OutsourceabilityKind = Literal[
    "Fully Outsourceable",
    "Partially Outsourceable",
    "Not Outsourceable",
]

PartialKind = Literal["percent", "fixed", "driver"]


@dataclass(frozen=True)
class ActivityProfession:
    """A single (activity, profession) pair from the workbook."""

    activity: str
    profession: str

    def as_mapping_key(self) -> str:
        """Return the same key shape used by JOB_FAMILY_MAPPING ("Activity - Profession")."""
        return f"{self.activity} - {self.profession}"


@dataclass
class PartialConfig:
    """How a Partially-Outsourceable family limits outsourcing.

    Exactly one of (percent / fixed_count / (driver_activity, driver_profession, max_ratio))
    should be populated, matched to ``kind``.
    """

    kind: PartialKind
    percent: float | None = None
    fixed_count: int | None = None
    driver_activity: str | None = None
    driver_profession: str | None = None
    max_ratio: str | None = None

    def is_valid(self) -> bool:
        if self.kind == "percent":
            return self.percent is not None and 0.0 <= self.percent <= 1.0
        if self.kind == "fixed":
            return self.fixed_count is not None and self.fixed_count >= 0
        if self.kind == "driver":
            return bool(self.driver_activity and self.driver_profession and self.max_ratio)
        return False


@dataclass
class CustomFamilyCosts:
    """Unit costs the LP uses when a user-defined family has no rows in the workbook."""

    saudi_inhouse: float
    non_saudi_inhouse: float
    outsourced: float


@dataclass
class CustomFamilySpec:
    """A user-defined job family.

    ``family_name`` is the canonical name (one entry can resolve many source pairs into
    the same family). ``source_pairs`` is the list of unmapped (activity, profession)
    pairs the user has decided belong to this family. If empty, the family exists only
    in target mode (a brand-new family with no rows in the workbook).
    """

    family_name: str
    outsourceability: OutsourceabilityKind
    source_pairs: list[ActivityProfession] = field(default_factory=list)
    partial_config: PartialConfig | None = None
    costs: CustomFamilyCosts | None = None

    def is_brand_new(self) -> bool:
        return not self.source_pairs


def merge_user_mappings(
    base_mapping: dict[str, str],
    custom_families: Iterable[CustomFamilySpec],
) -> dict[str, str]:
    """Return a copy of ``base_mapping`` with each family's ``source_pairs`` added.

    The user-supplied mappings always win when a key collides with the static mapping.
    Suitable for handing to :func:`manpower_app.mappings.get_job_family_with_fallback`
    as its ``exact_mapping`` argument.
    """
    merged = dict(base_mapping)
    for spec in custom_families:
        for pair in spec.source_pairs:
            merged[pair.as_mapping_key()] = spec.family_name
    return merged


def custom_families_by_name(
    custom_families: Iterable[CustomFamilySpec],
) -> dict[str, CustomFamilySpec]:
    return {spec.family_name: spec for spec in custom_families}
