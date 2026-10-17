"""What happens to Costco's operating margin without membership fees?

Costco reports three revenue lines in every 10-K: net sales (merchandise),
membership fees, and total revenue. Membership fees are small next to
merchandise sales -- under 2.5% of total revenue in every year here --
but the merchandise side runs close to cost, so the question is how much
of the operating profit is really the membership engine.

Counterfactual: subtract membership fees from operating income, holding
expenses flat. Membership does carry some cost (printing and mailing
cards, processing renewals), but Costco does not break that cost out and
the warehouses and staff would be there with or without the fee line --
so read the ex-fee profit as "profit if the fee revenue vanished and
nothing else changed," an approximate upper bound on the fees'
contribution, not a segment P&L.

Coverage: fiscal 2017 through fiscal 2026 (fiscal years end in late
August / early September; FY2023 was a 53-week year). Figures are
transcribed from the 10-K income statements in SOURCES.md and
cross-checked live against SEC EDGAR company facts for total revenue,
operating income, and net income at run time.
"""

import csv
import json
import os
import urllib.request
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
CIK = 909832  # Costco Wholesale Corp

# ---------------------------------------------------------------------------
# Costco 10-K consolidated statements of income ($M).
# fiscal year, year-end date, net sales, membership fees, total revenue,
# operating income, net income attributable to Costco. Sources in SOURCES.md.
# Every row checks: net sales + membership fees = total revenue.
# ---------------------------------------------------------------------------
COSTCO = [
    (2017, "2017-09-03", 126172, 2853, 129025, 4111, 2679),
    (2018, "2018-09-02", 138434, 3142, 141576, 4480, 3134),
    (2019, "2019-09-01", 149351, 3352, 152703, 4737, 3659),
    (2020, "2020-08-30", 163220, 3541, 166761, 5435, 4002),
    (2021, "2021-08-29", 192052, 3877, 195929, 6708, 5007),
    (2022, "2022-08-28", 222730, 4224, 226954, 7793, 5844),
    (2023, "2023-09-03", 237710, 4580, 242290, 8114, 6292),
    (2024, "2024-09-01", 249625, 4828, 254453, 9285, 7367),
    (2025, "2025-08-31", 269912, 5323, 275235, 10383, 8099),
    (2026, "2026-08-30", 297247, 5907, 303154, 11685, 9226),
]


def edgar_crosscheck():
    """Live SEC EDGAR company facts: total revenue, operating income and
    net income by fiscal year-end, to cross-check the transcribed table.

    Returns {year_end: (revenue_$M, op_income_$M, net_income_$M)} or {}
    if EDGAR is unreachable -- the 10-K table stands on its own.
    """
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{CIK:010d}.json"
    req = urllib.request.Request(
        url, headers={"User-Agent": "costco-membership-engine research"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            facts = json.loads(resp.read())["facts"]["us-gaap"]
    except Exception:
        return {}

    def annual(tag):
        out = {}
        for r in facts.get(tag, {}).get("units", {}).get("USD", []):
            if r.get("form") != "10-K" or "start" not in r:
                continue
            dur = (date.fromisoformat(r["end"])
                   - date.fromisoformat(r["start"])).days
            if dur < 300:
                continue
            prev = out.get(r["end"])
            if prev is None or r["filed"] > prev[0]:
                out[r["end"]] = (r["filed"], r["val"] / 1e6)
        return {end: val for end, (_f, val) in out.items()}

    # Total revenue tag changed names over the period; merge both.
    rev = {**annual("Revenues"),
           **annual("RevenueFromContractWithCustomerExcludingAssessedTax")}
    op = annual("OperatingIncomeLoss")
    net = annual("NetIncomeLoss")
    ends = set(rev) & set(op) & set(net)
    return {end: (rev[end], op[end], net[end]) for end in ends}


def main():
    rows = []
    for fy, end, sales, fees, total, op, net in COSTCO:
        assert sales + fees == total, f"FY{fy}: revenue lines do not add up"
        ex = op - fees
        rows.append({
            "fiscal_year": fy,
            "year_end": end,
            "net_sales_$M": sales,
            "membership_fees_$M": fees,
            "total_revenue_$M": total,
            "operating_income_$M": op,
            "net_income_$M": net,
            "fees_share_of_revenue_%": round(fees / total * 100, 2),
            "fees_share_of_op_income_%": round(fees / op * 100, 1),
            "op_income_ex_fees_$M": ex,
            "op_margin_%": round(op / total * 100, 2),
            "op_margin_ex_fees_%": round(ex / total * 100, 2),
            "note": ("counterfactual holds expenses flat: approximate upper "
                     "bound on fee contribution"),
        })

    with open(os.path.join(HERE, "results.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ---- chart: operating income vs ex-membership operating income --------
    yrs = [str(r["fiscal_year"]) for r in rows]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    x = range(len(yrs))
    ax.bar([i - 0.2 for i in x],
           [r["operating_income_$M"] / 1000 for r in rows],
           width=0.4, color="#1f4e79", label="Operating income (reported)")
    ax.bar([i + 0.2 for i in x],
           [r["op_income_ex_fees_$M"] / 1000 for r in rows],
           width=0.4, color="#b00020",
           label="Ex-membership-fee operating income (expenses held flat)")
    for i, r in enumerate(rows):
        ax.text(i, r["operating_income_$M"] / 1000 + 0.25,
                f"{r['fees_share_of_op_income_%']:.0f}%",
                ha="center", fontsize=8)
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"FY{y}" for y in yrs])
    ax.set_ylabel("$B")
    ax.set_title("Costco: operating income with and without membership fees\n"
                 "(label = fees as % of operating income)")
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "results.png"), dpi=120)
    plt.close(fig)

    # ---- printed findings --------------------------------------------------
    print("Costco Wholesale (10-K income statements, $M)")
    print(f"{'FY':<6}{'total rev':>10}{'fees':>8}{'fees/rev':>10}"
          f"{'op inc':>9}{'fees/op inc':>13}{'ex-fee op':>11}"
          f"{'margin':>8}{'ex-fee margin':>15}")
    for r in rows:
        print(f"{r['fiscal_year']:<6}{r['total_revenue_$M']:>10,}"
              f"{r['membership_fees_$M']:>8,}"
              f"{r['fees_share_of_revenue_%']:>9.2f}%"
              f"{r['operating_income_$M']:>9,}"
              f"{r['fees_share_of_op_income_%']:>12.1f}%"
              f"{r['op_income_ex_fees_$M']:>11,}"
              f"{r['op_margin_%']:>7.2f}%"
              f"{r['op_margin_ex_fees_%']:>14.2f}%")
    print()
    first, last = rows[0], rows[-1]
    print(f"Membership fees are only {last['fees_share_of_revenue_%']:.2f}% of "
          f"FY2026 revenue but {last['fees_share_of_op_income_%']:.1f}% of "
          f"operating income.")
    print(f"Without them (expenses held flat), FY2026 operating income falls "
          f"from ${last['operating_income_$M']/1000:.2f}B to "
          f"${last['op_income_ex_fees_$M']/1000:.2f}B and the operating "
          f"margin thins from {last['op_margin_%']:.2f}% to "
          f"{last['op_margin_ex_fees_%']:.2f}%.")
    print(f"The fee share of operating income has trended down: "
          f"{first['fees_share_of_op_income_%']:.1f}% in FY2017 to "
          f"{last['fees_share_of_op_income_%']:.1f}% in FY2026, because "
          f"ex-fee operating income grew from "
          f"${first['op_income_ex_fees_$M']/1000:.2f}B to "
          f"${last['op_income_ex_fees_$M']/1000:.2f}B -- the merchandise "
          f"business stands on its own better than it used to, but fees "
          f"still supply more than half of operating profit.")
    n_years = last["fiscal_year"] - first["fiscal_year"]
    fee_cagr = (last["membership_fees_$M"] / first["membership_fees_$M"]) \
        ** (1 / n_years) - 1
    rev_cagr = (last["total_revenue_$M"] / first["total_revenue_$M"]) \
        ** (1 / n_years) - 1
    print(f"FY2017-FY2026 growth: membership fees {fee_cagr*100:.1f}%/yr, "
          f"total revenue {rev_cagr*100:.1f}%/yr.")
    print(f"Costco stayed operating-profitable without fees in all "
          f"{len(rows)} years shown (thinnest: FY2017, "
          f"${rows[0]['op_income_ex_fees_$M']:,}M).")
    print()
    print("Caveats: fee counterfactual holds expenses flat (approximate "
          "upper bound); in reality losing the fee would also lose the "
          "members and their merchandise spending, which this does not "
          "model.")

    # ---- live EDGAR cross-check -------------------------------------------
    check = edgar_crosscheck()
    if check:
        matched, mismatched, checked = 0, [], 0
        for fy, end, _s, _f, total, op, net in COSTCO:
            if end in check:
                checked += 1
                rev_e, op_e, net_e = check[end]
                if (abs(rev_e - total) <= 1 and abs(op_e - op) <= 1
                        and abs(net_e - net) <= 1):
                    matched += 1
                else:
                    mismatched.append(fy)
        print()
        print(f"EDGAR cross-check: {matched} of {checked} fiscal years "
              f"match company facts on revenue, operating income and net "
              f"income (within $1M rounding)."
              + (f" MISMATCH: FY{mismatched}" if mismatched else ""))
    else:
        print()
        print("EDGAR cross-check unavailable this run; 10-K table stands "
              "alone (see SOURCES.md).")
    print()
    print("Sources: SOURCES.md (results.csv, results.png written).")


if __name__ == "__main__":
    main()
