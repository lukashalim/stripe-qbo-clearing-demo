"""
Intentionally WRONG QBO Journal Entry — Before / broken demo path.

Naive bookkeeper pattern:
  Credit Sales Revenue for gross
  Debit Checking for the FULL gross

Does NOT debit Merchant Fees.
Does NOT debit Stripe Clearing.

Fees and uncleared timing variance are invisible → bank reconciliation / P&L
mismatch vs reality. Contrast with post_qbo.py (After / correct path).
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import requests
from dotenv import load_dotenv

from post_qbo import QBO_SANDBOX_BASE, refresh_access_token

# Only Checking + Sales — fees/clearing are deliberately omitted.
REQUIRED_ENV = [
    "QBO_CLIENT_ID",
    "QBO_CLIENT_SECRET",
    "QBO_REFRESH_TOKEN",
    "QBO_REALM_ID",
    "CHECKING_ACCOUNT_ID",
    "SALES_REVENUE_ACCOUNT_ID",
]


def load_naive_env() -> dict[str, str]:
    """Load OAuth + Checking/Sales only (fees/clearing unused by design)."""
    load_dotenv()
    values: dict[str, str] = {}
    missing: list[str] = []
    for name in REQUIRED_ENV:
        raw = os.getenv(name, "").strip()
        if not raw or raw == "REPLACE_ME" or raw.endswith("REPLACE_ME"):
            missing.append(name)
        else:
            values[name] = raw
    if missing:
        print(
            "Missing or placeholder QBO env vars (naive path):\n  - "
            + "\n  - ".join(missing),
            file=sys.stderr,
        )
        sys.exit(1)
    return values


def build_naive_journal_lines(gross_dollars: float) -> list[dict[str, Any]]:
    """
    Two-line JE: Dr Checking (gross) / Cr Sales (gross).

    Balanced on purpose so QBO accepts it — wrong economically, not syntactically.
    """
    if gross_dollars <= 0:
        return []
    amount = round(float(gross_dollars), 2)
    return [
        {
            "bucket": "checking",
            "posting_type": "Debit",
            "amount": amount,
            "description": "NAIVE: Stripe gross → Checking (fees & clearing ignored)",
        },
        {
            "bucket": "sales",
            "posting_type": "Credit",
            "amount": amount,
            "description": "NAIVE: Stripe gross sales",
        },
    ]


def build_naive_je_body(gross_dollars: float, env: dict[str, str]) -> dict[str, Any]:
    """Assemble the QBO JournalEntry JSON payload (print / POST)."""
    lines = build_naive_journal_lines(gross_dollars)
    if not lines:
        raise ValueError("gross must be > 0 to build a naive journal entry")

    qbo_lines: list[dict[str, Any]] = []
    account_by_bucket = {
        "checking": env["CHECKING_ACCOUNT_ID"],
        "sales": env["SALES_REVENUE_ACCOUNT_ID"],
    }
    for line in lines:
        qbo_lines.append(
            {
                "DetailType": "JournalEntryLineDetail",
                "Amount": line["amount"],
                "Description": line["description"],
                "JournalEntryLineDetail": {
                    "PostingType": line["posting_type"],
                    "AccountRef": {"value": account_by_bucket[line["bucket"]]},
                },
            }
        )

    return {
        "DocNumber": "STRIPE-NAIVE",
        "PrivateNote": (
            "INTENTIONALLY WRONG — Stripe naive demo JE "
            "(gross to Checking; no fees / no clearing)"
        ),
        "Line": qbo_lines,
    }


def print_naive_payload(body: dict[str, Any]) -> None:
    print("=== INTENTIONALLY WRONG Journal Entry payload (dry-run) ===")
    print(json.dumps(body, indent=2))
    print()
    print(
        "This JE debits Checking for FULL GROSS and credits Sales — "
        "Merchant Fees and Stripe Clearing are NOT used."
    )


def post_naive_journal_entry(gross_dollars: float) -> dict[str, Any]:
    """Refresh OAuth and POST the deliberately broken 2-line sandbox JE."""
    env = load_naive_env()
    body = build_naive_je_body(gross_dollars, env)

    print("!!! POSTING INTENTIONALLY WRONG JE TO QBO SANDBOX !!!")
    print_naive_payload(body)

    access_token = refresh_access_token(
        env["QBO_CLIENT_ID"],
        env["QBO_CLIENT_SECRET"],
        env["QBO_REFRESH_TOKEN"],
    )

    realm = env["QBO_REALM_ID"]
    url = f"{QBO_SANDBOX_BASE}/v3/company/{realm}/journalentry"

    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        params={"minorversion": "65"},
        json=body,
        timeout=60,
    )

    if response.status_code >= 400:
        print(
            f"QBO JournalEntry POST failed ({response.status_code}):\n{response.text}",
            file=sys.stderr,
        )
        sys.exit(1)

    result = response.json()
    je = result.get("JournalEntry") or {}
    print("=== INTENTIONALLY WRONG QBO Journal Entry posted ===")
    print(f"  Id:         {je.get('Id')}")
    print(f"  DocNumber:  {je.get('DocNumber')}")
    print(f"  SyncToken:  {je.get('SyncToken')}")
    print(f"  Lines:      {len(je.get('Line') or body['Line'])}")
    return result


if __name__ == "__main__":
    print(
        "post_qbo_naive.py is a library. Run: python demo_broken.py [--post]",
        file=sys.stderr,
    )
    sys.exit(1)
