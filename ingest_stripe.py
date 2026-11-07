"""
Phase 2 / Step 1 — Pull Stripe BalanceTransactions into a local JSON cache.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import stripe
from dotenv import load_dotenv

RAW_CACHE_PATH = "raw_stripe_transactions.json"


def _configure_stripe() -> None:
    load_dotenv()
    key = os.getenv("STRIPE_TEST_SECRET_KEY", "").strip()
    if not key or key.startswith("sk_test_REPLACE"):
        print("Missing STRIPE_TEST_SECRET_KEY in .env", file=sys.stderr)
        sys.exit(1)
    stripe.api_key = key


def _serialize_balance_transaction(txn: stripe.BalanceTransaction) -> dict[str, Any]:
    """Flatten a BalanceTransaction into JSON-friendly primitives."""
    payout = txn.payout
    if payout is not None and not isinstance(payout, str):
        payout = getattr(payout, "id", None)

    source = txn.source
    if source is not None and not isinstance(source, str):
        source = getattr(source, "id", None)

    return {
        "id": txn.id,
        "object": txn.object,
        "amount": txn.amount,
        "fee": txn.fee,
        "net": txn.net,
        "currency": txn.currency,
        "type": txn.type,
        "status": txn.status,
        "description": txn.description,
        "created": txn.created,
        "available_on": txn.available_on,
        "source": source,
        "payout": payout,
        "reporting_category": getattr(txn, "reporting_category", None),
    }


def ingest(output_path: str = RAW_CACHE_PATH) -> list[dict[str, Any]]:
    """Paginate BalanceTransaction.list and write raw_stripe_transactions.json."""
    _configure_stripe()

    rows: list[dict[str, Any]] = []
    starting_after: str | None = None

    while True:
        params: dict[str, Any] = {"limit": 100}
        if starting_after:
            params["starting_after"] = starting_after

        page = stripe.BalanceTransaction.list(**params)
        for txn in page.data:
            rows.append(_serialize_balance_transaction(txn))

        if not page.has_more or not page.data:
            break
        starting_after = page.data[-1].id

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2)

    print(f"Ingested {len(rows)} balance transactions → {output_path}")
    return rows


if __name__ == "__main__":
    ingest()
