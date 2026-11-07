"""
Phase 2 orchestration — ingest → transform → post.

Does not run seed_stripe_test_data.py (keeps Before / After phases separate).
Fails fast when required environment variables are missing.
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

from ingest_stripe import ingest
from post_qbo import post_journal_entry
from transform_engine import transform

REQUIRED_ENV = [
    "STRIPE_TEST_SECRET_KEY",
    "QBO_CLIENT_ID",
    "QBO_CLIENT_SECRET",
    "QBO_REFRESH_TOKEN",
    "QBO_REALM_ID",
    "CHECKING_ACCOUNT_ID",
    "STRIPE_CLEARING_ACCOUNT_ID",
    "MERCHANT_FEES_ACCOUNT_ID",
    "SALES_REVENUE_ACCOUNT_ID",
]


def _is_placeholder(value: str) -> bool:
    v = value.strip()
    return (not v) or v == "REPLACE_ME" or v.endswith("REPLACE_ME") or "REPLACE_ME" in v


def assert_env() -> None:
    load_dotenv()
    missing = [name for name in REQUIRED_ENV if _is_placeholder(os.getenv(name, ""))]
    if missing:
        print(
            "Failing fast — missing or placeholder env vars:\n  - "
            + "\n  - ".join(missing),
            file=sys.stderr,
        )
        sys.exit(1)

    stripe_key = os.environ["STRIPE_TEST_SECRET_KEY"]
    if stripe_key.startswith("sk_live_"):
        print("Refusing live Stripe key in main.py. Use sk_test_… only.", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    print("Stripe → QBO clearing pipeline (After)\n")
    assert_env()

    print("--- Step 1: Ingest ---")
    ingest()

    print("\n--- Step 2: Transform ---")
    result = transform()

    print("\n--- Step 3: Post QBO Journal Entry ---")
    post_journal_entry(result)

    print("\nDone.")


if __name__ == "__main__":
    main()
