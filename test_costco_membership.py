"""Unit checks for the Costco membership engine calculations.

Run: python3 -m unittest test_costco_membership -v
No network: these test build_rows / sensitivity_rows only, not EDGAR.
"""
import unittest

from costco_membership import COSTCO, FEE_REALIZATIONS, build_rows, sensitivity_rows


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


if __name__ == "__main__":
    unittest.main()
