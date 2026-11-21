"""Unit checks for the Costco membership engine calculations.

Run: python3 -m unittest test_costco_membership -v
No network: these test the calculation builders only, not EDGAR.
"""
import unittest

from costco_membership import (
    COSTCO, ERAS, FEE_REALIZATIONS, build_cumulative, build_eras,
    build_growth, build_growth_rates, build_incremental,
    build_incremental_summary, build_margin_bridge,
    build_margin_bridge_summary, build_rows, build_stability,
    sensitivity_rows)


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

class TestCumulativeEras(unittest.TestCase):
    def setUp(self):
        self.rows = build_rows()
        self.cum = build_cumulative(self.rows)
        self.eras = build_eras(self.rows)

    def test_cumulative_shape_and_first_year(self):
        self.assertEqual(len(self.cum), len(self.rows))
        self.assertEqual(self.cum[0]["cum_membership_fees_$M"], 2853)
        self.assertEqual(self.cum[0]["cum_fees_share_of_op_income_%"], 69.4)

    def test_cumulative_last_equals_decade_totals(self):
        last = self.cum[-1]
        self.assertEqual(last["cum_membership_fees_$M"], 41627)
        self.assertEqual(last["cum_operating_income_$M"], 72731)
        self.assertEqual(last["cum_op_income_ex_fees_$M"], 31104)
        self.assertEqual(last["cum_total_revenue_$M"], 2088080)
        self.assertEqual(last["cum_fees_share_of_op_income_%"], 57.2)
        # totals equal sums of the level rows
        self.assertEqual(last["cum_membership_fees_$M"],
                         sum(r["membership_fees_$M"] for r in self.rows))
        self.assertEqual(last["cum_operating_income_$M"],
                         sum(r["operating_income_$M"] for r in self.rows))

    def test_cumulative_is_monotonic_and_splits(self):
        for prev, cur in zip(self.cum, self.cum[1:]):
            self.assertGreater(cur["cum_membership_fees_$M"],
                               prev["cum_membership_fees_$M"])
            self.assertGreater(cur["cum_operating_income_$M"],
                               prev["cum_operating_income_$M"])
        for c in self.cum:
            self.assertEqual(
                c["cum_membership_fees_$M"] + c["cum_op_income_ex_fees_$M"],
                c["cum_operating_income_$M"])

    def test_cumulative_share_peaks_fy2019_then_falls(self):
        shares = [c["cum_fees_share_of_op_income_%"] for c in self.cum]
        peak_i = shares.index(max(shares))
        self.assertEqual(self.cum[peak_i]["fiscal_year"], 2019)
        self.assertEqual(shares[peak_i], 70.1)
        self.assertEqual(shares[peak_i + 1:], sorted(shares[peak_i + 1:], reverse=True))

    def test_eras_shape_and_full_period_matches_cumulative(self):
        self.assertEqual(len(self.eras), len(ERAS))
        full = self.eras[-1]
        self.assertEqual(full["era"], "FY2017-FY2026 full period")
        self.assertEqual(full["membership_fees_$M"], 41627)
        self.assertEqual(full["operating_income_$M"], 72731)
        # first three eras partition the full period
        parts = self.eras[:3]
        self.assertEqual(sum(e["membership_fees_$M"] for e in parts), 41627)
        self.assertEqual(sum(e["operating_income_$M"] for e in parts), 72731)
        self.assertEqual(sum(e["years"] for e in parts), 10)

    def test_era_fee_share_falls_monotonically(self):
        shares = [e["fees_share_of_op_income_%"] for e in self.eras[:3]]
        self.assertEqual(shares, [70.1, 58.4, 52.3])

    def test_era_ex_fee_margin_rises_monotonically(self):
        margins = [e["op_margin_ex_fees_%"] for e in self.eras[:3]]
        self.assertEqual(margins, [0.94, 1.41, 1.75])


class TestIncremental(unittest.TestCase):
    def setUp(self):
        self.rows = build_rows()
        self.inc = build_incremental(self.rows)
        self.summary = build_incremental_summary(self.rows)[0]

    def test_shape_starts_fy2018(self):
        self.assertEqual(len(self.inc), len(self.rows) - 1)
        self.assertEqual(self.inc[0]["fiscal_year"], 2018)
        self.assertEqual(self.inc[-1]["fiscal_year"], 2026)

    def test_deltas_match_level_rows(self):
        for prev, cur, r in zip(self.rows, self.rows[1:], self.inc):
            self.assertEqual(r["net_sales_growth_$M"],
                             cur["net_sales_$M"] - prev["net_sales_$M"])
            self.assertEqual(r["op_income_growth_$M"],
                             cur["operating_income_$M"]
                             - prev["operating_income_$M"])
            self.assertEqual(
                r["fee_growth_$M"] + r["ex_fee_op_growth_$M"],
                r["op_income_growth_$M"])

    def test_components_sum_to_total_rate(self):
        for r in self.inc:
            self.assertAlmostEqual(
                r["fee_per_added_sales_%"] + r["ex_fee_incremental_margin_%"],
                r["incremental_op_margin_on_added_sales_%"], delta=0.02)
            self.assertAlmostEqual(
                r["incremental_op_margin_on_added_sales_%"],
                r["op_income_growth_$M"] / r["net_sales_growth_$M"] * 100,
                places=2)

    def test_decade_summary_hand_values(self):
        s = self.summary
        self.assertEqual(s["period"], "FY2017-FY2026")
        self.assertEqual(s["growth_years"], 9)
        self.assertEqual(s["net_sales_growth_$M"], 171075)
        self.assertEqual(s["fee_growth_$M"], 3054)
        self.assertEqual(s["ex_fee_op_growth_$M"], 4520)
        self.assertEqual(s["op_income_growth_$M"], 7574)
        self.assertEqual(s["incremental_op_margin_on_added_sales_%"], 4.43)
        self.assertEqual(s["fee_per_added_sales_%"], 1.79)
        self.assertEqual(s["ex_fee_incremental_margin_%"], 2.64)
        self.assertEqual(s["fee_share_of_op_growth_%"], 40.3)

    def test_summary_equals_first_to_last_levels(self):
        s = self.summary
        self.assertEqual(s["net_sales_growth_$M"],
                         self.rows[-1]["net_sales_$M"]
                         - self.rows[0]["net_sales_$M"])
        self.assertEqual(s["op_income_growth_$M"],
                         sum(r["op_income_growth_$M"] for r in self.inc))

    def test_fy2023_ex_fee_incremental_negative(self):
        fy23 = next(r for r in self.inc if r["fiscal_year"] == 2023)
        self.assertEqual(fy23["ex_fee_op_growth_$M"], -35)
        self.assertEqual(fy23["ex_fee_incremental_margin_%"], -0.23)
        self.assertGreater(fy23["fee_per_added_sales_%"],
                           fy23["incremental_op_margin_on_added_sales_%"])
        self.assertEqual(self.summary["negative_ex_fee_incremental_years"], 1)

    def test_range_and_fy2024_peak(self):
        self.assertEqual(self.summary["min_incremental_op_margin_%"], 2.14)
        self.assertEqual(self.summary["max_incremental_op_margin_%"], 9.83)
        peak = max(self.inc,
                   key=lambda r: r["incremental_op_margin_on_added_sales_%"])
        self.assertEqual(peak["fiscal_year"], 2024)

    def test_incremental_margin_above_level_margins(self):
        # decade incremental margin beats the ex-fee level margin in
        # both endpoint years and the FY2026 reported margin on sales
        s = self.summary
        self.assertGreater(s["incremental_op_margin_on_added_sales_%"],
                           self.rows[-1]["ex_fee_margin_on_net_sales_%"])
        self.assertGreater(s["ex_fee_incremental_margin_%"],
                           self.rows[-1]["ex_fee_margin_on_net_sales_%"])
        self.assertGreater(s["ex_fee_incremental_margin_%"],
                           self.rows[0]["ex_fee_margin_on_net_sales_%"])


class TestMarginBridge(unittest.TestCase):
    def setUp(self):
        self.rows = build_rows()
        self.bridge = build_margin_bridge(self.rows)
        self.summary = build_margin_bridge_summary(self.rows)[0]

    def test_shape_and_first_year_baseline(self):
        self.assertEqual(len(self.bridge), len(self.rows))
        first = self.bridge[0]
        self.assertEqual(first["fiscal_year"], 2017)
        self.assertEqual(first["fee_change_vs_FY2017_pts"], 0.0)
        self.assertEqual(first["ex_fee_change_vs_FY2017_pts"], 0.0)
        self.assertEqual(first["reported_change_vs_FY2017_pts"], 0.0)
        self.assertIsNone(first["reported_change_vs_prior_year_pts"])

    def test_parts_sum_to_reported_every_year(self):
        for b, r in zip(self.bridge, self.rows):
            self.assertAlmostEqual(
                b["fee_margin_pts"] + b["ex_fee_margin_pts"],
                b["reported_op_margin_pts"], delta=0.02)
            self.assertEqual(b["reported_op_margin_pts"],
                             r["op_margin_%"])
            self.assertEqual(b["fee_margin_pts"],
                             r["fees_share_of_revenue_%"])
            self.assertEqual(b["ex_fee_margin_pts"],
                             r["op_margin_ex_fees_%"])

    def test_changes_split_exactly(self):
        for b in self.bridge:
            self.assertAlmostEqual(
                b["fee_change_vs_FY2017_pts"]
                + b["ex_fee_change_vs_FY2017_pts"],
                b["reported_change_vs_FY2017_pts"], delta=0.02)
        for b in self.bridge[1:]:
            self.assertAlmostEqual(
                b["fee_change_vs_prior_year_pts"]
                + b["ex_fee_change_vs_prior_year_pts"],
                b["reported_change_vs_prior_year_pts"], delta=0.02)

    def test_yoy_changes_match_level_differences(self):
        for prev, cur in zip(self.bridge, self.bridge[1:]):
            self.assertAlmostEqual(
                cur["reported_change_vs_prior_year_pts"],
                cur["reported_op_margin_pts"]
                - prev["reported_op_margin_pts"], delta=0.02)

    def test_decade_summary_hand_values(self):
        s = self.summary
        self.assertEqual(s["period"], "FY2017-FY2026")
        self.assertEqual(s["reported_op_margin_start_pts"], 3.19)
        self.assertEqual(s["reported_op_margin_end_pts"], 3.85)
        self.assertEqual(s["reported_change_pts"], 0.67)
        self.assertEqual(s["fee_change_pts"], -0.26)
        self.assertEqual(s["ex_fee_change_pts"], 0.93)
        self.assertEqual(s["ex_fee_share_of_reported_change_%"], 139.3)

    def test_ex_fee_supplied_more_than_all_net_expansion(self):
        s = self.summary
        self.assertLess(s["fee_change_pts"], 0)
        self.assertGreater(s["ex_fee_change_pts"],
                           s["reported_change_pts"])
        self.assertGreater(s["ex_fee_share_of_reported_change_%"], 100)

    def test_troughs(self):
        s = self.summary
        self.assertEqual(s["fee_margin_trough_year"], 2022)
        self.assertEqual(s["fee_margin_trough_pts"], 1.86)
        self.assertEqual(s["ex_fee_margin_trough_year"], 2019)
        self.assertEqual(s["ex_fee_margin_trough_pts"], 0.91)

    def test_up_down_year_counts(self):
        s = self.summary
        self.assertEqual(s["reported_margin_up_years"], 6)
        self.assertEqual(s["reported_margin_down_years"], 3)
        self.assertEqual(
            s["reported_margin_up_years"]
            + s["reported_margin_down_years"],
            len(self.bridge) - 1)
        fy24 = next(b for b in self.bridge if b["fiscal_year"] == 2024)
        self.assertEqual(fy24["reported_change_vs_prior_year_pts"], 0.30)
        self.assertEqual(fy24["ex_fee_change_vs_prior_year_pts"], 0.29)


if __name__ == "__main__":

    unittest.main()
