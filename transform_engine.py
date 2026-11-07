"""
Phase 2 / Step 2 — DuckDB aggregation → balanced 4-line Journal Entry payload.

Debit Checking (cleared net) + Debit Fees + Debit Clearing (uncleared net)
  = Credit Sales (gross)
Amounts converted from Stripe cents to dollars.
"""

from __future__ import annotations

import json
import os
from typing import Any

import duckdb

RAW_CACHE_PATH = "raw_stripe_transactions.json"


def _cents_to_dollars(cents: int | float | None) -> float:
    if cents is None:
        return 0.0
    return round(float(cents) / 100.0, 2)


def load_raw(path: str = RAW_CACHE_PATH) -> list[dict[str, Any]]:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} not found. Run ingest_stripe first (or python main.py)."
        )
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"{path} must be a JSON array of balance transactions")
    return data


def aggregate(
    transactions: list[dict[str, Any]],
    path: str = RAW_CACHE_PATH,
) -> dict[str, float]:
    """
    Isolate gross sales, processing fees, cleared net (→ Checking),
    and uncleared variance (payout IS NULL → Stripe Clearing).
    """
    if not transactions:
        return {
            "gross": 0.0,
            "fees": 0.0,
            "checking_net": 0.0,
            "uncleared": 0.0,
        }

    con = duckdb.connect(database=":memory:")
    # Prefer the on-disk cache so DuckDB's JSON reader types null payouts correctly.
    con.execute(
        "CREATE TABLE balance_txns AS SELECT * FROM read_json_auto(?)",
        [path],
    )

    # Charge-type rows drive sales/fees/clearing. Fee is usually embedded on the charge txn.
    row = con.execute(
        """
        SELECT
          COALESCE(SUM(CASE WHEN type = 'charge' THEN amount ELSE 0 END), 0) AS gross_cents,
          COALESCE(SUM(CASE WHEN type = 'charge' THEN fee    ELSE 0 END), 0) AS fee_cents,
          COALESCE(
            SUM(CASE WHEN type = 'charge' AND payout IS NOT NULL THEN net ELSE 0 END),
            0
          ) AS cleared_net_cents,
          COALESCE(
            SUM(CASE WHEN type = 'charge' AND payout IS NULL THEN net ELSE 0 END),
            0
          ) AS uncleared_net_cents
        FROM balance_txns
        """
    ).fetchone()

    gross_cents, fee_cents, cleared_net_cents, uncleared_net_cents = row
    totals = {
        "gross": _cents_to_dollars(gross_cents),
        "fees": _cents_to_dollars(fee_cents),
        "checking_net": _cents_to_dollars(cleared_net_cents),
        "uncleared": _cents_to_dollars(uncleared_net_cents),
    }

    debit_sum = round(
        totals["checking_net"] + totals["fees"] + totals["uncleared"], 2
    )
    credit_sum = totals["gross"]
    if abs(debit_sum - credit_sum) > 0.01:
        raise ValueError(
            f"JE out of balance: debits={debit_sum} credits={credit_sum} "
            f"(checking={totals['checking_net']}, fees={totals['fees']}, "
            f"clearing={totals['uncleared']}, sales={totals['gross']})"
        )

    return totals


def build_journal_lines(totals: dict[str, float]) -> list[dict[str, Any]]:
    """
    Emit QBO JournalEntry line stubs (account IDs filled in by post_qbo).
    Skip zero-amount lines so QBO accepts the payload when a bucket is empty.
    """
    specs = [
        ("checking", "Debit", totals["checking_net"], "Stripe cleared net → Checking"),
        ("fees", "Debit", totals["fees"], "Stripe processing fees"),
        ("clearing", "Debit", totals["uncleared"], "Stripe clearing (uncleared / payout null)"),
        ("sales", "Credit", totals["gross"], "Stripe gross sales"),
    ]

    lines: list[dict[str, Any]] = []
    for bucket, posting_type, amount, description in specs:
        if amount == 0:
            continue
        lines.append(
            {
                "bucket": bucket,
                "posting_type": posting_type,
                "amount": amount,
                "description": description,
            }
        )
    return lines


def transform(path: str = RAW_CACHE_PATH) -> dict[str, Any]:
    transactions = load_raw(path)
    totals = aggregate(transactions, path=path)
    lines = build_journal_lines(totals)

    print("=== Transform (DuckDB) ===")
    print(f"  Gross sales:     ${totals['gross']:.2f}")
    print(f"  Fees:            ${totals['fees']:.2f}")
    print(f"  Checking (net):  ${totals['checking_net']:.2f}")
    print(f"  Uncleared:       ${totals['uncleared']:.2f}")
    print(f"  JE lines:        {len(lines)} (zeros skipped)")

    return {"totals": totals, "lines": lines}


if __name__ == "__main__":
    transform()
