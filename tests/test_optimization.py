from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd

from manpower_app.optimization import (
    IN_HOUSE_NON_SAUDI_COLUMN,
    IN_HOUSE_SAUDI_COLUMN,
    OUTSOURCED_COLUMN,
    solve_optimization,
)
from manpower_app.service import OptimizationSettings, process_workbook, run_optimization
from manpower_app.terminology import OUTSOURCED_UNIT_COST_BASIS_COLUMN


def base_row(**overrides):
    row = {
        "Job Family": "Generic Role",
        "Outsourceability Type": "Partially Outsourceable",
        "Current Headcount": 100,
        "Minimum Headcount Needed": 80,
        "Risk Factor": 0.25,
        "Outsourced v1": 80,
        "Current Total In-house Saudi": 0,
        "Tenured Saudi In-House": 0,
        "Tenured Non-Saudi In-House": 0,
        "Fully Loaded Cost per In-house Saudi Employee": 100.0,
        "Fully Loaded Cost per In-house Non-Saudi Employee": 10.0,
        OUTSOURCED_UNIT_COST_BASIS_COLUMN: 1.0,
    }
    row.update(overrides)
    return row


class OptimizationLPTests(unittest.TestCase):
    def solve_one(self, row):
        data = pd.DataFrame([row])
        solved, payroll, status = solve_optimization(
            data,
            enforce_saudization=True,
            saudization_rate=0.0,
            can_reduce_current_saudi=True,
            tenure_constraint_active=False,
            profession_saudization_rates={},
        )
        return solved.iloc[0], payroll, status

    def test_risk_adjusted_minimum_allows_outsourced_above_inhouse_minimum(self):
        row, _, status = self.solve_one(base_row())

        outsourced = int(row[OUTSOURCED_COLUMN])
        inhouse = int(row[IN_HOUSE_NON_SAUDI_COLUMN] + row[IN_HOUSE_SAUDI_COLUMN])
        effective_count = outsourced * (1 - row["Risk Factor"]) + inhouse

        self.assertEqual(status, "Optimal")
        self.assertEqual(outsourced, 80)
        self.assertEqual(inhouse, 20)
        self.assertGreaterEqual(effective_count, row["Minimum Headcount Needed"])
        self.assertLess(inhouse, row["Minimum Headcount Needed"])

    def test_higher_risk_factor_lowers_outsourced_cap(self):
        row, _, _ = self.solve_one(base_row(**{"Risk Factor": 0.5, "Outsourced v1": 40}))

        self.assertEqual(int(row[OUTSOURCED_COLUMN]), 40)
        self.assertEqual(int(row[IN_HOUSE_NON_SAUDI_COLUMN] + row[IN_HOUSE_SAUDI_COLUMN]), 60)

    def test_current_saudi_floor_is_enforced_when_reduction_is_disabled(self):
        data = pd.DataFrame([base_row(**{"Current Total In-house Saudi": 5})])
        solved, _, status = solve_optimization(
            data,
            enforce_saudization=True,
            saudization_rate=0.0,
            can_reduce_current_saudi=False,
            tenure_constraint_active=False,
            profession_saudization_rates={},
        )

        self.assertEqual(status, "Optimal")
        self.assertGreaterEqual(int(solved.iloc[0][IN_HOUSE_SAUDI_COLUMN]), 5)

    def test_engineer_family_is_locked_in_house(self):
        # Engineer is "Not Outsourceable": max_outsourced = 0 regardless of cost,
        # so the LP is forced to keep all 100 in-house.
        row, _, status = self.solve_one(
            base_row(**{"Job Family": "Engineer", "Outsourceability Type": "Not Outsourceable"})
        )
        self.assertEqual(status, "Optimal")
        self.assertEqual(int(row[OUTSOURCED_COLUMN]), 0)
        self.assertEqual(
            int(row[IN_HOUSE_NON_SAUDI_COLUMN] + row[IN_HOUSE_SAUDI_COLUMN]), 100
        )

    def test_clerk_caps_outsourcing_at_total_minus_hq_count(self):
        # HQ-fixed rule: outsource cap = total - HQ_count, ignoring Outsourced v1.
        # 100 total, 30 HQ Clerks -> max 70 outsourced (LP picks the cap to minimize cost).
        row, _, status = self.solve_one(
            base_row(
                **{
                    "Job Family": "Clerk",
                    "HQ Inhouse Count": 30,
                    "Outsourced v1": 5,  # would normally cap at 5 — must be ignored for HQ-fixed
                }
            )
        )
        self.assertEqual(status, "Optimal")
        self.assertEqual(int(row[OUTSOURCED_COLUMN]), 70)
        self.assertEqual(
            int(row[IN_HOUSE_NON_SAUDI_COLUMN] + row[IN_HOUSE_SAUDI_COLUMN]), 30
        )

    def test_controller_full_inhouse_when_total_below_hq_count(self):
        # Edge case: planned headcount drops below the current HQ count.
        # All workers stay in-house (max_outsourced = max(0, total - HQ) = 0).
        row, _, status = self.solve_one(
            base_row(
                **{
                    "Job Family": "Controller",
                    "Current Headcount": 8,
                    "HQ Inhouse Count": 12,
                    "Minimum Headcount Needed": 8,
                    "Outsourced v1": 10,
                }
            )
        )
        self.assertEqual(status, "Optimal")
        self.assertEqual(int(row[OUTSOURCED_COLUMN]), 0)
        self.assertEqual(
            int(row[IN_HOUSE_NON_SAUDI_COLUMN] + row[IN_HOUSE_SAUDI_COLUMN]), 8
        )


class SoftInputOverrideTests(unittest.TestCase):
    """Tests for the user-tunable assumptions (Saudi premium, outsource discount, max ratios)."""

    def test_saudi_cost_premium_changes_inhouse_split(self):
        from manpower_app.costs import calculate_inhouse_cost_split

        # With premium = 1.10 (default): Saudi = 1.10 * non-Saudi.
        default_split = calculate_inhouse_cost_split(100.0, 1, 1)
        self.assertAlmostEqual(
            default_split["Fully Loaded Cost per In-house Saudi Employee"]
            / default_split["Fully Loaded Cost per In-house Non-Saudi Employee"],
            1.10,
            places=6,
        )

        # With premium = 1.50: Saudi = 1.50 * non-Saudi.
        custom_split = calculate_inhouse_cost_split(100.0, 1, 1, saudi_premium=1.50)
        self.assertAlmostEqual(
            custom_split["Fully Loaded Cost per In-house Saudi Employee"]
            / custom_split["Fully Loaded Cost per In-house Non-Saudi Employee"],
            1.50,
            places=6,
        )

    def test_outsource_cost_discount_replaces_workbook_cost(self):
        # Round-trip through the full pipeline: with the override on, the outsource cost basis
        # is (1 - discount) * non-Saudi in-house cost — independent of the workbook value.
        if not Path("/Users/bkaaki001/Downloads/Manpower (1).xlsx").exists():
            self.skipTest("comparison workbook not available")
        processed = process_workbook("/Users/bkaaki001/Downloads/Manpower (1).xlsx")

        baseline = run_optimization(processed, OptimizationSettings())
        cheap = run_optimization(
            processed,
            OptimizationSettings(outsource_cost_discount=0.50),
        )

        # When outsourcing is half the cost of non-Saudi in-house, the optimizer outsources at
        # least as many workers as in the baseline (cost dropped, never any reason to outsource less).
        self.assertGreaterEqual(
            cheap["results"]["total_outsourced_final"],
            baseline["results"]["total_outsourced_final"],
        )

    def test_max_ratio_override_changes_minimum_headcount(self):
        # Tighten the Quarries Foreman ratio from 1:15 to 1:5; min-headcount should grow ~3x.
        if not Path("/Users/bkaaki001/Downloads/Manpower (1).xlsx").exists():
            self.skipTest("comparison workbook not available")
        processed = process_workbook("/Users/bkaaki001/Downloads/Manpower (1).xlsx")
        data_default, _ = __import__(
            "manpower_app.service", fromlist=["prepare_model_data"]
        ).prepare_model_data(processed, OptimizationSettings())
        data_tight, _ = __import__(
            "manpower_app.service", fromlist=["prepare_model_data"]
        ).prepare_model_data(
            processed,
            OptimizationSettings(max_ratio_overrides={"Quarries Foreman": "1:5"}),
        )

        default_min = int(
            data_default[data_default["Job Family"] == "Quarries Foreman"]["Minimum Headcount Needed"].iloc[0]
        )
        tight_min = int(
            data_tight[data_tight["Job Family"] == "Quarries Foreman"]["Minimum Headcount Needed"].iloc[0]
        )
        self.assertGreater(tight_min, default_min)


WORKBOOK = Path("/Users/bkaaki001/Downloads/Manpower (1).xlsx")


@unittest.skipUnless(WORKBOOK.exists(), "comparison workbook is not available on this machine")
class WorkbookRegressionTests(unittest.TestCase):
    def test_default_workbook_matches_pinned_savings_baseline(self):
        processed = process_workbook(str(WORKBOOK))
        payload = run_optimization(processed, OptimizationSettings())

        self.assertEqual(payload["metadata"]["optimization_status"], "Optimal")
        self.assertAlmostEqual(payload["metadata"]["optimized_savings"], 0.014917296126, places=9)
        self.assertEqual(int(payload["results"]["total_outsourced_final"]), 7865)
        self.assertFalse(payload["audit"]["Risk-Adjusted Minimum Met"].eq(False).any())


class Tier5IntegrationTests(unittest.TestCase):
    """Integration tests for the Tier 5 features: unmapped reporting, custom-family
    plumbing, and target-mode optimization. Build a tiny in-memory workbook so the
    tests do not depend on the regression file."""

    @staticmethod
    def _make_workbook_bytes(*, include_unmapped: bool = False) -> bytes:
        import io
        from openpyxl import Workbook

        wb = Workbook()
        inhouse = wb.active
        inhouse.title = "Inhouse"
        inhouse.append([
            "No", "Location", "Profession", "Nationality", "Total Paid", "Total Unpaid",
        ])
        # Two known mappings: Factory + Operator -> Factory Operator; Head Office + Clerk -> Clerk.
        inhouse.append([1, "Production", "Operator", "Saudi", 5000, 0])
        inhouse.append([2, "Production", "Operator", "non-saudi", 4000, 0])
        inhouse.append([3, "Head Office", "Clerk", "SAUDI", 3000, 0])
        if include_unmapped:
            inhouse.append([4, "Production", "Astronaut", "Saudi", 4000, 0])

        sub = wb.create_sheet("Subcontractor")
        sub.append([
            "No", "Working in", "Profession", "Nationality", "Basic",
            "Housing Paid", "Trans Paid", "Food", "Gosi", "Value O.T (SAR)",
            "Government Fees", "E.O.S monthly", "Service Margin",
        ])
        # One subcontractor row in the same Production-Operator family.
        sub.append([100, "Production", "Operator", "non-saudi", 1000, 200, 100, 50, 0, 0, 0, 0, 100])

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf.read()

    def test_unmapped_pairs_are_reported_not_raised(self):
        """process_workbook should not raise on unknown pairs; should surface them
        through ProcessedWorkbook.unmapped_pairs."""
        import io
        from manpower_app.service import process_workbook

        contents = self._make_workbook_bytes(include_unmapped=True)
        processed = process_workbook(io.BytesIO(contents))
        # Astronaut is not in JOB_FAMILY_MAPPING -> it should appear in unmapped_pairs.
        pairs = [(p["activity"], p["profession"]) for p in processed.unmapped_pairs]
        self.assertIn(("Factory", "Astronaut"), pairs)
        # Mapped families are still in the optimization frame.
        self.assertIn("Factory Operator", set(processed.optimization_df["Job Family"]))

    def test_custom_mapping_resolves_unmapped_pair(self):
        """When the user supplies a CustomFamilySpec covering an unmapped pair, the
        pair should be resolved on re-process and the family should appear in the
        optimization frame."""
        import io
        from manpower_app.family_specs import (
            ActivityProfession,
            CustomFamilySpec,
            CustomFamilyCosts,
        )
        from manpower_app.service import process_workbook

        contents = self._make_workbook_bytes(include_unmapped=True)
        custom = [
            CustomFamilySpec(
                family_name="Astro Operator",
                outsourceability="Partially Outsourceable",
                source_pairs=[ActivityProfession(activity="Factory", profession="Astronaut")],
                costs=CustomFamilyCosts(
                    saudi_inhouse=5000, non_saudi_inhouse=4500, outsourced=4000
                ),
            )
        ]
        processed = process_workbook(io.BytesIO(contents), custom_families=custom)
        self.assertEqual(processed.unmapped_pairs, [])
        self.assertIn("Astro Operator", set(processed.optimization_df["Job Family"]))

    def test_target_mode_replaces_current_headcount_for_named_family(self):
        """In target mode, the LP's headcount-balance equality should be against the
        user-supplied target, not the workbook's current count."""
        import io
        from manpower_app.service import (
            OptimizationSettings,
            process_workbook,
            run_optimization,
        )

        contents = self._make_workbook_bytes()
        processed = process_workbook(io.BytesIO(contents))
        settings = OptimizationSettings(
            optimization_mode="target",
            target_headcounts={"Factory Operator": 9},  # baseline is 3 (2 inhouse + 1 sub)
            can_reduce_current_saudi=True,  # avoid Saudi floor making the LP infeasible
        )
        payload = run_optimization(processed, settings)
        rows = payload["data"]
        operator_row = rows[rows["Job Family"] == "Factory Operator"].iloc[0]
        total_split = (
            int(operator_row[OUTSOURCED_COLUMN])
            + int(operator_row[IN_HOUSE_NON_SAUDI_COLUMN])
            + int(operator_row[IN_HOUSE_SAUDI_COLUMN])
        )
        self.assertEqual(total_split, 9)
        # Savings should NOT be in the metadata in target mode.
        self.assertNotIn("optimized_savings", payload["metadata"])
        self.assertEqual(payload["metadata"]["optimization_mode"], "target")

    def test_brand_new_family_with_costs_shows_up_in_results(self):
        """A user-defined family with no rows in the workbook gets injected by
        process_workbook using the user's costs, and its target headcount drives the LP."""
        import io
        from manpower_app.family_specs import CustomFamilyCosts, CustomFamilySpec
        from manpower_app.service import (
            OptimizationSettings,
            process_workbook,
            run_optimization,
        )

        contents = self._make_workbook_bytes()
        new_family = CustomFamilySpec(
            family_name="Drone Pilot",
            outsourceability="Partially Outsourceable",
            source_pairs=[],
            costs=CustomFamilyCosts(saudi_inhouse=8000, non_saudi_inhouse=7000, outsourced=5000),
        )
        processed = process_workbook(io.BytesIO(contents), custom_families=[new_family])
        self.assertIn("Drone Pilot", set(processed.optimization_df["Job Family"]))

        settings = OptimizationSettings(
            optimization_mode="target",
            target_headcounts={"Drone Pilot": 5},
            custom_families=[new_family],
            can_reduce_current_saudi=True,
        )
        payload = run_optimization(processed, settings)
        rows = payload["data"]
        drone_row = rows[rows["Job Family"] == "Drone Pilot"].iloc[0]
        total_split = (
            int(drone_row[OUTSOURCED_COLUMN])
            + int(drone_row[IN_HOUSE_NON_SAUDI_COLUMN])
            + int(drone_row[IN_HOUSE_SAUDI_COLUMN])
        )
        self.assertEqual(total_split, 5)


if __name__ == "__main__":
    unittest.main()
