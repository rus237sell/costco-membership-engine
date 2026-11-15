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

v2 adds two cuts on the same verified table, no new external data:
(1) Replacement sales -- how much extra net sales, earned at that year's
ex-fee merchandise margin (ex-fee operating income / net sales), it
would take to replace the full fee line. (2) Fee sensitivity -- operating
income and margin at 100/75/50/25/0% fee realization for every year.

v3 adds growth attribution, also on the same table: every year-over-year
change in operating income splits exactly into the change in membership
fees plus the change in ex-fee (merchandise) operating income, because
operating income is fees plus ex-fee operating income by construction.
That split shows who carried profit growth each year, and cumulatively
over the decade -- a different question from the level shares in v1.

v4 adds a stability cut, also on the same table: the year-over-year
growth rates of fees, ex-fee operating income, and reported operating
income, summarized by mean, population standard deviation, range, and
down years over the nine growth years FY2018-FY2026. The level and
growth cuts say fees are large and carried early growth; this cut asks
how steady each line is -- whether the fee line behaves like a stable
annuity next to a volatile merchandise business.

v5 adds a cumulative / era lens, also on the same table: yearly rows
cumulated from FY2017, and pooled into three eras (FY2017-FY2019
pre-pandemic, FY2020-FY2022 pandemic surge, FY2023-FY2026 post-surge).
Annual fee shares swing with each year's merchandise result; cumulating
and pooling show whether the long-run dependence on fees is actually
falling, and how much of the decade's profit the fee line supplied in
total rather than in any single year.

v6 adds an incremental-margin / operating-leverage cut, also on the
same table: each year's change in operating income divided by that
year's change in net sales, split exactly into the fee component and
the ex-fee merchandise component (the two changes sum to the operating
income change, so their per-sales-dollar rates sum too). The level
margins in v1 say what profit Costco keeps on all sales; this cut asks
what it kept on the sales it added -- and because fees carry no
merchandise cost, a fee line that is under 2% of incremental sales can
still supply two fifths of incremental profit.

Coverage: fiscal 2017 through fiscal 2026 (fiscal years end in late
August / early September; FY2023 was a 53-week year). Figures are
transcribed from the 10-K income statements in SOURCES.md and
cross-checked live against SEC EDGAR company facts for total revenue,
operating income, and net income at run time.
"""

import csv
import json
import os
import statistics
import urllib.request
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
CIK = 909832  # Costco Wholesale Corp
FEE_REALIZATIONS = (100, 75, 50, 25, 0)

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


def build_rows(data=COSTCO):
    """One results row per fiscal year, including the v2 replacement cut.

    Replacement sales = fees / ex-fee merchandise margin, where the
    merchandise margin is ex-fee operating income divided by net sales.
    It answers: at the margin the merchandise business actually earns
    without fees, how much more merchandise would Costco have to sell
    to make up the entire fee line?
    """
    rows = []
    for fy, end, sales, fees, total, op, net in data:
        assert sales + fees == total, f"FY{fy}: revenue lines do not add up"
        ex = op - fees
        merch_margin = ex / sales if sales and ex > 0 else None
        replacement = round(fees / merch_margin) if merch_margin else None
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
            "ex_fee_margin_on_net_sales_%": (
                round(merch_margin * 100, 2) if merch_margin else None),
            "replacement_net_sales_$M": replacement,
            "replacement_sales_%_of_net_sales": (
                round(replacement / sales * 100, 1) if replacement else None),
            "note": ("counterfactual holds expenses flat: approximate upper "
                     "bound on fee contribution"),
        })
    return rows


def sensitivity_rows(rows):
    """Operating income/margin if only part of the fee line is realized.

    Margin uses reported total revenue as the denominator, matching
    results.csv, so the 100% row equals reported and the 0% row equals
    the ex-fee row exactly.
    """
    out = []
    for r in rows:
        ex = r["op_income_ex_fees_$M"]
        fees = r["membership_fees_$M"]
        total = r["total_revenue_$M"]
        for pct in FEE_REALIZATIONS:
            recognized = round(fees * pct / 100)
            op_scenario = ex + recognized
            out.append({
                "fiscal_year": r["fiscal_year"],
                "fee_realization_%": pct,
                "fees_recognized_$M": recognized,
                "operating_income_$M": op_scenario,
                "op_margin_on_reported_revenue_%": round(
                    op_scenario / total * 100, 2),
            })
    return out


def build_growth(rows):
    """Year-over-year growth attribution for operating income.

    Operating income = membership fees + ex-fee operating income, so each
    year's change splits exactly: delta_op = delta_fees + delta_ex_fee.
    The fee share of a year's growth can exceed 100% (or be negative)
    when the other component moves the opposite way -- FY2023 is the
    case here: ex-fee income fell $35M while fees rose $356M. Cumulative
    columns run from the first year in the table.
    """
    out = []
    cum_fees = cum_ex = cum_op = 0
    for prev, cur in zip(rows, rows[1:]):
        d_op = cur["operating_income_$M"] - prev["operating_income_$M"]
        d_fees = (cur["membership_fees_$M"]
                  - prev["membership_fees_$M"])
        d_ex = (cur["op_income_ex_fees_$M"]
                - prev["op_income_ex_fees_$M"])
        assert d_fees + d_ex == d_op
        cum_fees += d_fees
        cum_ex += d_ex
        cum_op += d_op
        out.append({
            "fiscal_year": cur["fiscal_year"],
            "op_income_growth_$M": d_op,
            "fee_growth_$M": d_fees,
            "ex_fee_op_growth_$M": d_ex,
            "fee_share_of_op_growth_%": (
                round(d_fees / d_op * 100, 1) if d_op else None),
            "cum_op_growth_since_FY2017_$M": cum_op,
            "cum_fee_growth_since_FY2017_$M": cum_fees,
            "cum_ex_fee_growth_since_FY2017_$M": cum_ex,
            "cum_fee_share_of_op_growth_%": (
                round(cum_fees / cum_op * 100, 1) if cum_op else None),
        })
    return out


def build_growth_rates(rows):
    """Year-over-year growth rates (%) for fees, ex-fee and reported
    operating income, FY2018 onward."""
    out = []
    for prev, cur in zip(rows, rows[1:]):
        out.append({
            "fiscal_year": cur["fiscal_year"],
            "fee_growth_%": round(
                (cur["membership_fees_$M"] / prev["membership_fees_$M"]
                 - 1) * 100, 2),
            "ex_fee_op_growth_%": round(
                (cur["op_income_ex_fees_$M"] / prev["op_income_ex_fees_$M"]
                 - 1) * 100, 2),
            "op_income_growth_%": round(
                (cur["operating_income_$M"] / prev["operating_income_$M"]
                 - 1) * 100, 2),
        })
    return out


def build_stability(rows):
    """Stability summary per series over the nine growth years.

    Standard deviation is the population stdev of the nine observed
    growth years (the full period studied, not a sample from it).
    A series can average faster growth and still be the riskier line:
    what matters here is the spread around that average and whether
    the line ever shrinks.
    """
    series = [
        ("membership_fees", "fee_growth_%"),
        ("ex_fee_operating_income", "ex_fee_op_growth_%"),
        ("operating_income", "op_income_growth_%"),
    ]
    out = []
    for name, key in series:
        raw = []
        col = {
            "fee_growth_%": "membership_fees_$M",
            "ex_fee_op_growth_%": "op_income_ex_fees_$M",
            "op_income_growth_%": "operating_income_$M",
        }[key]
        for prev, cur in zip(rows, rows[1:]):
            raw.append((cur[col] / prev[col] - 1) * 100)
        out.append({
            "series": name,
            "growth_years": len(raw),
            "mean_yoy_growth_%": round(statistics.mean(raw), 2),
            "growth_stdev_pts": round(statistics.pstdev(raw), 2),
            "min_yoy_growth_%": round(min(raw), 2),
            "max_yoy_growth_%": round(max(raw), 2),
            "range_pts": round(max(raw) - min(raw), 2),
            "negative_growth_years": sum(1 for v in raw if v < 0),
        })
    return out



def build_cumulative(rows):
    """Cumulative totals from the first year in the table.

    Each row cumulates fees, operating income, ex-fee operating income
    and total revenue, so the cumulative fee share shows the long-run
    dependence on fees without single-year merchandise noise. It peaks
    at 70.1% through FY2019 and then falls every year to 57.2% through
    FY2026, even though the annual share also started at 69.4%.
    """
    out = []
    cum_fees = cum_op = cum_ex = cum_rev = 0
    for r in rows:
        cum_fees += r["membership_fees_$M"]
        cum_op += r["operating_income_$M"]
        cum_ex += r["op_income_ex_fees_$M"]
        cum_rev += r["total_revenue_$M"]
        out.append({
            "fiscal_year": r["fiscal_year"],
            "cum_membership_fees_$M": cum_fees,
            "cum_operating_income_$M": cum_op,
            "cum_op_income_ex_fees_$M": cum_ex,
            "cum_total_revenue_$M": cum_rev,
            "cum_fees_share_of_op_income_%": round(cum_fees / cum_op * 100, 1) if cum_op else None,
            "cum_op_margin_%": round(cum_op / cum_rev * 100, 2) if cum_rev else None,
            "cum_op_margin_ex_fees_%": round(cum_ex / cum_rev * 100, 2) if cum_rev else None,
        })
    return out


ERAS = (
    ("FY2017-FY2019 pre-pandemic", 2017, 2019),
    ("FY2020-FY2022 pandemic surge", 2020, 2022),
    ("FY2023-FY2026 post-surge", 2023, 2026),
    ("FY2017-FY2026 full period", 2017, 2026),
)


def build_eras(rows):
    """Pooled era totals: dollar-weighted, so big recent years count
    for more than small early ones, unlike a simple average of annual
    percentages."""
    out = []
    by_year = {r["fiscal_year"]: r for r in rows}
    for name, start, end in ERAS:
        sel = [by_year[y] for y in range(start, end + 1) if y in by_year]
        fees = sum(r["membership_fees_$M"] for r in sel)
        op = sum(r["operating_income_$M"] for r in sel)
        ex = sum(r["op_income_ex_fees_$M"] for r in sel)
        rev = sum(r["total_revenue_$M"] for r in sel)
        out.append({
            "era": name,
            "years": len(sel),
            "membership_fees_$M": fees,
            "operating_income_$M": op,
            "op_income_ex_fees_$M": ex,
            "total_revenue_$M": rev,
            "fees_share_of_op_income_%": round(fees / op * 100, 1) if op else None,
            "fees_share_of_revenue_%": round(fees / rev * 100, 2) if rev else None,
            "op_margin_%": round(op / rev * 100, 2) if rev else None,
            "op_margin_ex_fees_%": round(ex / rev * 100, 2) if rev else None,
        })
    return out


def build_incremental(rows):
    """Incremental margin per year: profit change per added sales dollar.

    For each year from FY2018: delta operating income / delta net sales,
    split into fee and ex-fee components over the same denominator.
    delta_op = delta_fees + delta_ex_fee by construction, so the two
    component rates sum to the total rate (to rounding). Fees are
    divided by merchandise sales growth even though they are not sales:
    that is the point -- it measures how much pure fee drop-through
    each added merchandise dollar brought with it.
    """
    out = []
    for prev, cur in zip(rows, rows[1:]):
        d_sales = cur["net_sales_$M"] - prev["net_sales_$M"]
        d_fees = (cur["membership_fees_$M"]
                  - prev["membership_fees_$M"])
        d_ex = (cur["op_income_ex_fees_$M"]
                - prev["op_income_ex_fees_$M"])
        d_op = cur["operating_income_$M"] - prev["operating_income_$M"]
        assert d_fees + d_ex == d_op
        out.append({
            "fiscal_year": cur["fiscal_year"],
            "net_sales_growth_$M": d_sales,
            "fee_growth_$M": d_fees,
            "ex_fee_op_growth_$M": d_ex,
            "op_income_growth_$M": d_op,
            "incremental_op_margin_on_added_sales_%": (
                round(d_op / d_sales * 100, 2) if d_sales else None),
            "fee_per_added_sales_%": (
                round(d_fees / d_sales * 100, 2) if d_sales else None),
            "ex_fee_incremental_margin_%": (
                round(d_ex / d_sales * 100, 2) if d_sales else None),
        })
    return out


def build_incremental_summary(rows):
    """Decade aggregate of the incremental cut: first-to-last changes.

    A single row pooling all nine growth years (dollar-weighted, like
    the era cut), so the decade incremental margin is total profit
    growth over total sales growth, not an average of annual rates.
    """
    first, last = rows[0], rows[-1]
    d_sales = last["net_sales_$M"] - first["net_sales_$M"]
    d_fees = last["membership_fees_$M"] - first["membership_fees_$M"]
    d_ex = (last["op_income_ex_fees_$M"]
            - first["op_income_ex_fees_$M"])
    d_op = last["operating_income_$M"] - first["operating_income_$M"]
    assert d_fees + d_ex == d_op
    inc = build_incremental(rows)
    rates = [r["incremental_op_margin_on_added_sales_%"] for r in inc]
    ex_rates = [r["ex_fee_incremental_margin_%"] for r in inc]
    return [{
        "period": f"FY{first['fiscal_year']}-FY{last['fiscal_year']}",
        "growth_years": len(inc),
        "net_sales_growth_$M": d_sales,
        "fee_growth_$M": d_fees,
        "ex_fee_op_growth_$M": d_ex,
        "op_income_growth_$M": d_op,
        "incremental_op_margin_on_added_sales_%": round(
            d_op / d_sales * 100, 2),
        "fee_per_added_sales_%": round(d_fees / d_sales * 100, 2),
        "ex_fee_incremental_margin_%": round(d_ex / d_sales * 100, 2),
        "fee_share_of_op_growth_%": round(d_fees / d_op * 100, 1),
        "min_incremental_op_margin_%": min(rates),
        "max_incremental_op_margin_%": max(rates),
        "negative_ex_fee_incremental_years": sum(
            1 for v in ex_rates if v < 0),
    }]


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


def write_csv(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    rows = build_rows()
    write_csv(os.path.join(HERE, "results.csv"), rows)
    sens = sensitivity_rows(rows)
    write_csv(os.path.join(HERE, "sensitivity.csv"), sens)
    growth = build_growth(rows)
    write_csv(os.path.join(HERE, "growth.csv"), growth)
    rates = build_growth_rates(rows)
    write_csv(os.path.join(HERE, "growth_rates.csv"), rates)
    stability = build_stability(rows)
    write_csv(os.path.join(HERE, "stability.csv"), stability)
    cumulative = build_cumulative(rows)
    write_csv(os.path.join(HERE, "cumulative.csv"), cumulative)
    eras = build_eras(rows)
    write_csv(os.path.join(HERE, "eras.csv"), eras)
    incremental = build_incremental(rows)
    write_csv(os.path.join(HERE, "incremental.csv"), incremental)
    inc_summary = build_incremental_summary(rows)
    write_csv(os.path.join(HERE, "incremental_summary.csv"), inc_summary)

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

    # ---- chart: replacement sales burden ----------------------------------
    fig, ax = plt.subplots(figsize=(9, 4.2))
    vals = [r["replacement_sales_%_of_net_sales"] for r in rows]
    ax.bar(list(x), vals, width=0.6, color="#1f4e79")
    for i, v in enumerate(vals):
        ax.text(i, v + 5, f"{v:.0f}%", ha="center", fontsize=8)
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"FY{y}" for y in yrs])
    ax.set_ylabel("% of that year's net sales")
    ax.set_title("Extra net sales needed to replace all membership fees\n"
                 "(at that year's ex-fee merchandise margin)")
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "replacement.png"), dpi=120)
    plt.close(fig)

    # ---- chart: growth attribution ----------------------------------------
    fig, ax = plt.subplots(figsize=(9, 4.2))
    gx = range(len(growth))
    ax.bar(gx, [g["fee_growth_$M"] / 1000 for g in growth],
           width=0.6, color="#1f4e79", label="Membership fee growth")
    ax.bar(gx, [g["ex_fee_op_growth_$M"] / 1000 for g in growth],
           width=0.6,
           bottom=[g["fee_growth_$M"] / 1000 for g in growth],
           color="#b00020",
           label="Ex-fee (merchandise) operating income growth")
    ax.axhline(0, color="black", linewidth=0.8)
    for i, g in enumerate(growth):
        ax.text(i, g["op_income_growth_$M"] / 1000 + 0.06,
                f"{g['fee_share_of_op_growth_%']:.0f}%",
                ha="center", fontsize=8)
    ax.set_xticks(list(gx))
    ax.set_xticklabels([f"FY{g['fiscal_year']}" for g in growth])
    ax.set_ylabel("$B change vs prior year")
    ax.set_title("Costco operating income growth, split by source\n"
                 "(label = fees as % of that year's growth)")
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "growth.png"), dpi=120)
    plt.close(fig)

    # ---- chart: growth-rate stability --------------------------------------
    fig, ax = plt.subplots(figsize=(9, 4.2))
    rx = range(len(rates))
    ax.plot(rx, [r["fee_growth_%"] for r in rates], marker="o",
            color="#1f4e79", label="Membership fee growth")
    ax.plot(rx, [r["ex_fee_op_growth_%"] for r in rates], marker="o",
            color="#b00020", label="Ex-fee operating income growth")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(list(rx))
    ax.set_xticklabels([f"FY{r['fiscal_year']}" for r in rates])
    ax.set_ylabel("YoY growth %")
    ax.set_title("Costco growth stability: fees vs ex-fee operating income\n"
                 "(fee growth stayed in a 5.4% to 11.0% band; ex-fee swung "
                 "-1.0% to +49.5%)")
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "stability.png"), dpi=120)
    plt.close(fig)

    # ---- chart: cumulative lens -------------------------------------------
    fig, ax = plt.subplots(figsize=(9, 4.2))
    cx = range(len(cumulative))
    ax.plot(cx, [c["cum_operating_income_$M"] / 1000 for c in cumulative],
            marker="o", color="#1f4e79", label="Cumulative operating income")
    ax.plot(cx, [c["cum_op_income_ex_fees_$M"] / 1000 for c in cumulative],
            marker="o", color="#b00020",
            label="Cumulative ex-fee operating income")
    for i, c in enumerate(cumulative):
        ax.text(i, c["cum_operating_income_$M"] / 1000 + 2,
                f"{c['cum_fees_share_of_op_income_%']:.1f}%",
                ha="center", fontsize=8)
    ax.set_xticks(list(cx))
    ax.set_xticklabels([f"FY{c['fiscal_year']}" for c in cumulative])
    ax.set_ylabel("Cumulative $B")
    ax.set_title("Costco cumulative profit with and without fees\n"
                 "(label = cumulative fees as % of cumulative operating income)")
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "cumulative.png"), dpi=120)
    plt.close(fig)

    # ---- chart: incremental margin ----------------------------------------
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ix = range(len(incremental))
    ax.bar(ix, [r["fee_per_added_sales_%"] for r in incremental],
           width=0.6, color="#1f4e79",
           label="Fee growth per added net sales $")
    ax.bar(ix, [r["ex_fee_incremental_margin_%"] for r in incremental],
           width=0.6,
           bottom=[r["fee_per_added_sales_%"] for r in incremental],
           color="#b00020",
           label="Ex-fee incremental margin")
    ax.axhline(0, color="black", linewidth=0.8)
    for i, r in enumerate(incremental):
        total = r["incremental_op_margin_on_added_sales_%"]
        ax.text(i, total + 0.25, f"{total:.1f}%", ha="center", fontsize=8)
    ax.set_xticks(list(ix))
    ax.set_xticklabels([f"FY{r['fiscal_year']}" for r in incremental])
    ax.set_ylabel("% of that year's added net sales")
    ax.set_title("Costco incremental margin: profit kept on added sales\n"
                 "(label = total incremental operating margin)")
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "incremental.png"), dpi=120)
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
    peak = max(rows, key=lambda r: r["replacement_sales_%_of_net_sales"])
    print(f"Replacement sales: at the ex-fee merchandise margin "
          f"({first['ex_fee_margin_on_net_sales_%']:.2f}% of net sales in "
          f"FY2017, {last['ex_fee_margin_on_net_sales_%']:.2f}% in FY2026), "
          f"replacing all fees would have taken an extra "
          f"${first['replacement_net_sales_$M']/1000:.0f}B of net sales in "
          f"FY2017 ({first['replacement_sales_%_of_net_sales']:.1f}% of that "
          f"year's net sales; peak {peak['replacement_sales_%_of_net_sales']:.1f}% "
          f"in FY{peak['fiscal_year']}) and an extra "
          f"${last['replacement_net_sales_$M']/1000:.0f}B in FY2026 "
          f"({last['replacement_sales_%_of_net_sales']:.1f}%). The dollar "
          f"amount barely moved; the burden halved because the merchandise "
          f"margin roughly doubled and sales more than doubled.")
    fy26_sens = [s for s in sens if s["fiscal_year"] == 2026]
    half = next(s for s in fy26_sens if s["fee_realization_%"] == 50)
    print(f"Fee sensitivity (FY2026): at 50% fee realization operating "
          f"income is ${half['operating_income_$M']/1000:.2f}B "
          f"({half['op_margin_on_reported_revenue_%']:.2f}% margin on "
          f"reported revenue); even at 0% it stays positive at "
          f"${last['op_income_ex_fees_$M']/1000:.2f}B in every year tested.")
    print()
    decade = growth[-1]
    early = growth[:2]
    fy23 = next(g for g in growth if g["fiscal_year"] == 2023)
    print(f"Growth attribution: of the "
          f"${decade['cum_op_growth_since_FY2017_$M']/1000:.2f}B operating "
          f"income growth from FY2017 to FY2026, fee growth supplied "
          f"${decade['cum_fee_growth_since_FY2017_$M']/1000:.2f}B "
          f"({decade['cum_fee_share_of_op_growth_%']:.1f}%) and ex-fee "
          f"merchandise growth supplied "
          f"${decade['cum_ex_fee_growth_since_FY2017_$M']/1000:.2f}B -- "
          f"fees are about half the level of profit but only about two "
          f"fifths of its growth. Early on fees carried growth "
          f"({early[0]['fee_share_of_op_growth_%']:.1f}% in FY2018 and "
          f"{early[1]['fee_share_of_op_growth_%']:.1f}% in FY2019); in "
          f"FY2023 fees supplied "
          f"{fy23['fee_share_of_op_growth_%']:.1f}% of growth because "
          f"ex-fee income fell ${-fy23['ex_fee_op_growth_$M']}M while "
          f"fees rose ${fy23['fee_growth_$M']}M.")
    print()
    stab = {s["series"]: s for s in stability}
    fees_s = stab["membership_fees"]
    ex_s = stab["ex_fee_operating_income"]
    ratio = ex_s["growth_stdev_pts"] / fees_s["growth_stdev_pts"]
    print(f"Stability: over FY2018-FY2026 fee growth averaged "
          f"{fees_s['mean_yoy_growth_%']:.2f}%/yr with a "
          f"{fees_s['growth_stdev_pts']:.2f}-pt standard deviation and "
          f"never fell (range {fees_s['min_yoy_growth_%']:.2f}% to "
          f"{fees_s['max_yoy_growth_%']:.2f}%). Ex-fee operating income "
          f"grew faster on average ({ex_s['mean_yoy_growth_%']:.2f}%/yr) "
          f"but with a {ex_s['growth_stdev_pts']:.2f}-pt standard "
          f"deviation -- about {ratio:.0f}x the fee line's -- ranging "
          f"{ex_s['min_yoy_growth_%']:.2f}% to "
          f"{ex_s['max_yoy_growth_%']:.2f}% with "
          f"{ex_s['negative_growth_years']} down year. The fee line is "
          f"the slow, steady half of operating profit; the merchandise "
          f"line supplies most of the growth and nearly all of the swing.")
    print()
    cum_last = cumulative[-1]
    era_pre, era_surge, era_late = eras[0], eras[1], eras[2]
    cum_peak = max(cumulative, key=lambda c: c["cum_fees_share_of_op_income_%"])
    print(f"Cumulative / era lens: over FY2017-FY2026 Costco collected "
          f"${cum_last['cum_membership_fees_$M']/1000:.1f}B of membership "
          f"fees against ${cum_last['cum_operating_income_$M']/1000:.1f}B "
          f"of operating income, so fees supplied "
          f"{cum_last['cum_fees_share_of_op_income_%']:.1f}% of the "
          f"decade's operating profit in total and cumulative ex-fee "
          f"operating income was "
          f"${cum_last['cum_op_income_ex_fees_$M']/1000:.1f}B. The "
          f"cumulative fee share peaked at "
          f"{cum_peak['cum_fees_share_of_op_income_%']:.1f}% through "
          f"FY{cum_peak['fiscal_year']} and fell every year after to "
          f"{cum_last['cum_fees_share_of_op_income_%']:.1f}%. By era the "
          f"fee share fell monotonically: "
          f"{era_pre['fees_share_of_op_income_%']:.1f}% pre-pandemic "
          f"(FY2017-FY2019), {era_surge['fees_share_of_op_income_%']:.1f}% "
          f"in the pandemic surge (FY2020-FY2022), and "
          f"{era_late['fees_share_of_op_income_%']:.1f}% post-surge "
          f"(FY2023-FY2026), while the ex-fee operating margin rose from "
          f"{era_pre['op_margin_ex_fees_%']:.2f}% to "
          f"{era_surge['op_margin_ex_fees_%']:.2f}% to "
          f"{era_late['op_margin_ex_fees_%']:.2f}% -- the merchandise "
          f"business strengthened in every era, so the falling fee share "
          f"is a denominator story, not a shrinking fee line.")
    print()
    inc_s = inc_summary[0]
    fy23i = next(r for r in incremental
                 if r["fiscal_year"] == 2023)
    fy24i = next(r for r in incremental
                 if r["fiscal_year"] == 2024)
    print(f"Incremental margin: over FY2017-FY2026 Costco added "
          f"${inc_s['net_sales_growth_$M']/1000:.1f}B of net sales and "
          f"${inc_s['op_income_growth_$M']/1000:.2f}B of operating "
          f"income -- an incremental operating margin of "
          f"{inc_s['incremental_op_margin_on_added_sales_%']:.2f}% on "
          f"added sales, above the level margin in either endpoint "
          f"year. Fees supplied just "
          f"{inc_s['fee_per_added_sales_%']:.2f}% of added sales but "
          f"{inc_s['fee_share_of_op_growth_%']:.1f}% of added profit, "
          f"because fee growth drops through with no merchandise cost; "
          f"the ex-fee incremental margin was "
          f"{inc_s['ex_fee_incremental_margin_%']:.2f}%, well above the "
          f"ex-fee level margin (1.00% of net sales in FY2017, 1.94% in "
          f"FY2026), so the merchandise business also leveraged its "
          f"growth. The annual cut is volatile: the total incremental "
          f"margin ran from "
          f"{inc_s['min_incremental_op_margin_%']:.2f}% to "
          f"{inc_s['max_incremental_op_margin_%']:.2f}% "
          f"({fy24i['incremental_op_margin_on_added_sales_%']:.2f}% in "
          f"FY2024), and in FY2023 ex-fee profit fell "
          f"${-fy23i['ex_fee_op_growth_$M']}M on "
          f"${fy23i['net_sales_growth_$M']/1000:.1f}B of added sales "
          f"(ex-fee incremental margin "
          f"{fy23i['ex_fee_incremental_margin_%']:.2f}%), so fees "
          f"supplied more than all of that year's incremental profit.")
    print()
    print("Caveats: fee counterfactual holds expenses flat (approximate "
          "upper bound); in reality losing the fee would also lose the "
          "members and their merchandise spending, which this does not "
          "model. Replacement sales assumes new sales earn the same "
          "ex-fee margin as existing sales, with no added fixed cost.")

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
    print("Sources: SOURCES.md (results.csv, sensitivity.csv, growth.csv, "
          "growth_rates.csv, stability.csv, results.png, replacement.png, "
          "growth.png, stability.png, cumulative.csv, eras.csv, "
          "cumulative.png, incremental.csv, incremental_summary.csv, "
          "incremental.png written).")


if __name__ == "__main__":
    main()
