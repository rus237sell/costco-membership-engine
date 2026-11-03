"""Unit checks for the Costco membership engine calculations.

Run: python3 -m unittest test_costco_membership -v
No network: these test the calculation builders only, not EDGAR.
"""
import unittest

from costco_membership import (
    COSTCO, FEE_REALIZATIONS, build_growth, build_growth_rates, build_rows,
    build_stability, sensitivity_rows)


class TestBuildRows(unittest.TestCase):
    def setUp(self):
        self.rows = build_rows()

    def test_revenue_lines_add_up(self):
        for raw, row in zip(COSTCO, self.rows):
            self.assertEqual(raw[2] + raw[3], raw[4])
            self.assertEqual(row["total_revenue_$M"], raw[4])

    def test_ex_fee_is_op_minus_fees(self):
        for row in self.rows:
            self.assertEqual(
                row["op_income_ex_fees_$M"],
                row["operating_income_$M"] - row["membership_fees_$M"])

    def test_profitable_without_fees_every_year(self):
        for row in self.rows:
            self.assertGreater(row["op_income_ex_fees_$M"], 0)

    def test_replacement_sales_recovers_fees(self):
        # replacement sales x ex-fee merchandise margin ~= fees (to rounding)
        for row in self.rows:
            margin = row["ex_fee_margin_on_net_sales_%"] / 100
            recovered = row["replacement_net_sales_$M"] * margin
            self.assertAlmostEqual(
                recovered, row["membership_fees_$M"],
                delta=row["membership_fees_$M"] * 0.01)

    def test_replacement_burden_fell_over_decade(self):
        self.assertLess(
            self.rows[-1]["replacement_sales_%_of_net_sales"],
            self.rows[0]["replacement_sales_%_of_net_sales"])


class TestSensitivity(unittest.TestCase):
    def setUp(self):
        self.rows = build_rows()
        self.sens = sensitivity_rows(self.rows)

    def test_shape(self):
        self.assertEqual(len(self.sens), len(self.rows) * len(FEE_REALIZATIONS))

    def test_endpoints_match_reported_and_ex_fee(self):
        by_year = {}
        for s in self.sens:
            by_year.setdefault(s["fiscal_year"], {})[s["fee_realization_%"]] = s
        for row in self.rows:
            ends = by_year[row["fiscal_year"]]
            self.assertEqual(ends[100]["operating_income_$M"],
                             row["operating_income_$M"])
            self.assertEqual(ends[0]["operating_income_$M"],
                             row["op_income_ex_fees_$M"])
            self.assertEqual(ends[0]["op_margin_on_reported_revenue_%"],
                             row["op_margin_ex_fees_%"])

    def test_monotonic_in_realization(self):
        by_year = {}
        for s in self.sens:
            by_year.setdefault(s["fiscal_year"], []).append(s)
        for year_rows in by_year.values():
            ops = [s["operating_income_$M"] for s in year_rows]
            self.assertEqual(ops, sorted(ops, reverse=True))


class TestGrowth(unittest.TestCase):
    def setUp(self):
        self.rows = build_rows()
        self.growth = build_growth(self.rows)

    def test_shape_starts_fy2018(self):
        self.assertEqual(len(self.growth), len(self.rows) - 1)
        self.assertEqual(self.growth[0]["fiscal_year"], 2018)
        self.assertEqual(self.growth[-1]["fiscal_year"], 2026)

    def test_split_is_exact_every_year(self):
        for g in self.growth:
            self.assertEqual(
                g["fee_growth_$M"] + g["ex_fee_op_growth_$M"],
                g["op_income_growth_$M"])

    def test_deltas_match_level_rows(self):
        for prev, cur, g in zip(self.rows, self.rows[1:], self.growth):
            self.assertEqual(g["op_income_growth_$M"],
                             cur["operating_income_$M"]
                             - prev["operating_income_$M"])
            self.assertEqual(g["fee_growth_$M"],
                             cur["membership_fees_$M"]
                             - prev["membership_fees_$M"])

    def test_decade_totals(self):
        last = self.growth[-1]
        self.assertEqual(last["cum_op_growth_since_FY2017_$M"], 7574)
        self.assertEqual(last["cum_fee_growth_since_FY2017_$M"], 3054)
        self.assertEqual(last["cum_ex_fee_growth_since_FY2017_$M"], 4520)
        self.assertEqual(last["cum_fee_share_of_op_growth_%"], 40.3)
        # cumulative columns equal first-to-last level differences
        self.assertEqual(
            last["cum_op_growth_since_FY2017_$M"],
            self.rows[-1]["operating_income_$M"]
            - self.rows[0]["operating_income_$M"])

    def test_fy2023_fees_carried_all_growth(self):
        fy23 = next(g for g in self.growth if g["fiscal_year"] == 2023)
        self.assertEqual(fy23["ex_fee_op_growth_$M"], -35)
        self.assertEqual(fy23["fee_growth_$M"], 356)
        self.assertGreater(fy23["fee_share_of_op_growth_%"], 100)

    def test_early_years_fee_led(self):
        shares = {g["fiscal_year"]: g["fee_share_of_op_growth_%"]
                  for g in self.growth}
        self.assertEqual(shares[2018], 78.3)
        self.assertEqual(shares[2019], 81.7)


class TestStability(unittest.TestCase):
    def setUp(self):
        self.rows = build_rows()
        self.rates = build_growth_rates(self.rows)
        self.stab = {s["series"]: s for s in build_stability(self.rows)}

    def test_shape(self):
        self.assertEqual(len(self.rates), len(self.rows) - 1)
        self.assertEqual(self.rates[0]["fiscal_year"], 2018)
        self.assertEqual(self.rates[-1]["fiscal_year"], 2026)
        self.assertEqual(set(self.stab), {
            "membership_fees", "ex_fee_operating_income",
            "operating_income"})
        for s in self.stab.values():
            self.assertEqual(s["growth_years"], 9)

    def test_rates_match_levels(self):
        for prev, cur, r in zip(self.rows, self.rows[1:], self.rates):
            self.assertAlmostEqual(
                r["fee_growth_%"],
                (cur["membership_fees_$M"] / prev["membership_fees_$M"]
                 - 1) * 100, places=2)
            self.assertAlmostEqual(
                r["ex_fee_op_growth_%"],
                (cur["op_income_ex_fees_$M"]
                 / prev["op_income_ex_fees_$M"] - 1) * 100, places=2)

    def test_fee_growth_never_negative_and_in_band(self):
        fees = self.stab["membership_fees"]
        self.assertEqual(fees["negative_growth_years"], 0)
        self.assertEqual(fees["min_yoy_growth_%"], 5.41)
        self.assertEqual(fees["max_yoy_growth_%"], 10.97)
        for r in self.rates:
            self.assertGreater(r["fee_growth_%"], 0)

    def test_ex_fee_swing_hand_values(self):
        ex = self.stab["ex_fee_operating_income"]
        self.assertEqual(ex["negative_growth_years"], 1)
        self.assertEqual(ex["min_yoy_growth_%"], -0.98)
        self.assertEqual(ex["max_yoy_growth_%"], 49.47)
        self.assertEqual(ex["range_pts"], 50.45)

    def test_summary_stats_hand_values(self):
        fees = self.stab["membership_fees"]
        ex = self.stab["ex_fee_operating_income"]
        self.assertEqual(fees["mean_yoy_growth_%"], 8.44)
        self.assertEqual(fees["growth_stdev_pts"], 1.94)
        self.assertEqual(ex["mean_yoy_growth_%"], 19.45)
        self.assertEqual(ex["growth_stdev_pts"], 15.61)

    def test_ex_fee_far_more_volatile_than_fees(self):
        ratio = (self.stab["ex_fee_operating_income"]["growth_stdev_pts"]
                 / self.stab["membership_fees"]["growth_stdev_pts"])
        self.assertGreater(ratio, 7)

    def test_range_is_max_minus_min(self):
        for s in self.stab.values():
            self.assertAlmostEqual(
                s["range_pts"],
                s["max_yoy_growth_%"] - s["min_yoy_growth_%"], places=2)


if __name__ == "__main__":
    unittest.main()
