# Sources

All figures are Costco's reported totals from its 10-K consolidated
statements of income ($M), not estimates. The counterfactual in the
script (operating income minus membership fees, expenses held flat) is
labeled as such wherever it appears.

## Costco Wholesale Corp 10-K income statements (SEC EDGAR, CIK 909832)

Each 10-K prints three fiscal years; the table in the script is built
from the overlapping statements so every year appears in at least two
filings, and every row checks net sales + membership fees = total
revenue.

- FY2017-FY2019: 10-K for fiscal 2019 (filed Oct 2019). Net sales
  126,172 / 138,434 / 149,351; membership fees 2,853 / 3,142 / 3,352;
  operating income 4,111 / 4,480 / 4,737.
- FY2020-FY2021: 10-K for fiscal 2021 (filed Oct 2021). Net sales
  163,220 / 192,052; membership fees 3,541 / 3,877; operating income
  5,435 / 6,708.
- FY2022-FY2023: 10-K for fiscal 2023 (filed Oct 2023). Net sales
  222,730 / 237,710; membership fees 4,224 / 4,580; operating income
  7,793 / 8,114. FY2023 was a 53-week year.
- FY2024-FY2025: 10-K for fiscal 2025 (filed Oct 7, 2025). Net sales
  249,625 / 269,912; membership fees 4,828 / 5,323; total revenue
  254,453 / 275,235; operating income 9,285 / 10,383.
- FY2026: 10-K for fiscal 2026 (filed Oct 6, 2026). Net sales 297,247;
  membership fees 5,907; total revenue 303,154; operating income
  11,685; net income 9,226.

## SEC EDGAR cross-check

- Company facts API (data.sec.gov), CIK 909832:
  RevenueFromContractWithCustomerExcludingAssessedTax (total revenue),
  OperatingIncomeLoss, and NetIncomeLoss, 10-K fiscal-year frames,
  pulled live by the script at run time and compared to the table
  within $1M rounding.
- Note: EDGAR's standard us-gaap tags stop separating net sales from
  membership fees after FY2017 (the membership-fee tag
  RevenueFromEnrollmentAndRegistrationFeesExcludingHospitalityEnterprises
  ends at FY2017, where it confirms the table: $2,853M), which is why
  the split itself is transcribed from the 10-K statements above.
