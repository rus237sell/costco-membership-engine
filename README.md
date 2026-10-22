# Costco membership engine

**Goal:** Test what happens to Costco's operating margin without membership fee income, using its reported 10-K revenue split (net sales vs membership fees) for fiscal 2017 to 2026.

**Macro steps:**
1. Transcribed net sales, membership fees, total revenue, operating income, and net income from Costco's 10-K income statements (FY2017-FY2026); every row checks net sales + membership fees = total revenue.
2. Ran a counterfactual: operating income minus membership fees, expenses held flat. That is an approximate upper bound on the fees' contribution, since membership carries some small cost Costco does not break out; it also does not model losing the members' merchandise spending.
3. Cross-checked total revenue, operating income, and net income live against SEC EDGAR company facts: 10 of 10 fiscal years match within $1M rounding.
4. Wrote the table to `results.csv` and charted reported vs ex-fee operating income (`results.png`).
5. v2: Added replacement sales (extra net sales needed, at that year's ex-fee merchandise margin, to replace all fees) to `results.csv` and `replacement.png`, plus a fee sensitivity table (`sensitivity.csv`: 100/75/50/25/0% realization for every year), and unit tests for the calculations.

**Versions:**
- v1: initial analysis.
- v2: replacement-sales and fee-sensitivity cuts on the same verified table (no new external data), plus tests. Replacement burden fell from 227% of net sales in FY2017 to 102% in FY2026.

**Short results:** Membership fees are under 2.5% of revenue in every year (1.95% in FY2026), but they equal 50.6% of FY2026 operating income ($5.91B of $11.69B). Without them (expenses held flat), FY2026 operating income halves to $5.78B and the operating margin thins from 3.85% to 1.91%. The dependence is shrinking: fees were 69.4% of operating income in FY2017, and ex-fee operating income grew from $1.26B to $5.78B over the decade, so Costco stayed operating-profitable without fees in all 10 years, thinnest in FY2017-FY2019 at about a 0.9% margin. Fees grew 8.4%/yr against 10.0%/yr for total revenue. Replacement cut: at the ex-fee merchandise margin (1.00% of net sales in FY2017, 1.94% in FY2026), replacing all fees would have taken an extra $286B of net sales in FY2017 (227% of that year's sales, peak 242% in FY2019) and an extra $304B in FY2026 (102%) — the dollars barely moved, the burden halved. At 50% fee realization, FY2026 operating income would still be $8.73B.

Run: `python3 costco_membership.py` (tests: `python3 -m unittest test_costco_membership -v`)
