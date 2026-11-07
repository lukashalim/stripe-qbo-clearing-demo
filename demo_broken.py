"""
Before / broken demo path for the B2B video.

INTENTIONALLY WRONG accounting:
  sum charge gross only → debit Checking (full gross) / credit Sales
  No Merchant Fees line. No Stripe Clearing line.

Default is print-only (dry-run). Pass --post to actually create a sandbox JE.
The correct After path remains: python main.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from dotenv import load_dotenv

from ingest_stripe import RAW_CACHE_PATH, ingest
from post_qbo_naive import (
    build_naive_je_body,
    load_naive_env,
    post_naive_journal_entry,
    print_naive_payload,
)


BANNER = """
############################################################
#  INTENTIONALLY WRONG — Before / broken demo beat         #
#  Gross → Checking only. Fees & clearing are invisible.   #
#  Do NOT use this for real books. Contrast: python main.py#
############################################################
"""


def _cents_to_dollars(cents: int | float) -> float:
    return round(float(cents) / 100.0, 2)


def sum_gross_only(path: str = RAW_CACHE_PATH) -> float:
    """Naive transform: sum charge amounts (gross). Ignore fee, net, payout."""
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} not found. Re-run with ingest, or provide the cache file."
        )
    with open(path, encoding="utf-8") as fh:
        rows = json.load(fh)
    if not isinstance(rows, list):
        raise ValueError(f"{path} must be a JSON array")

    gross_cents = 0
    charge_count = 0
    for row in rows:
        if row.get("type") == "charge":
            gross_cents += int(row.get("amount") or 0)
            charge_count += 1

    gross = _cents_to_dollars(gross_cents)
    print("=== Naive transform (GROSS ONLY — INTENTIONALLY WRONG) ===")
    print(f"  Charge rows:     {charge_count}")
    print(f"  Gross total:     ${gross:.2f}")
    print("  Fees:            IGNORED")
    print("  Checking net:    IGNORED (using full gross instead)")
    print("  Uncleared:       IGNORED")
    return gross


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Before/broken Stripe→QBO demo. Default: print naive JE only. "
            "Pass --post to create it in QBO sandbox."
        )
    )
    parser.add_argument(
        "--post",
        action="store_true",
        help="Actually POST the intentionally wrong Journal Entry to QBO sandbox",
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help=f"Reuse existing {RAW_CACHE_PATH} instead of pulling Stripe again",
    )
    parser.add_argument(
        "--cache",
        default=RAW_CACHE_PATH,
        help=f"Path to raw Stripe JSON cache (default: {RAW_CACHE_PATH})",
    )
    args = parser.parse_args(argv)

    # Windows consoles often default to a legacy code page; keep banners printable.
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    print(BANNER)

    load_dotenv()
    stripe_key = os.getenv("STRIPE_TEST_SECRET_KEY", "").strip()
    if not args.skip_ingest:
        if not stripe_key or stripe_key.startswith("sk_test_REPLACE"):
            print("Missing STRIPE_TEST_SECRET_KEY in .env", file=sys.stderr)
            sys.exit(1)
        if stripe_key.startswith("sk_live_"):
            print(
                "Refusing live Stripe key in demo_broken.py. Use sk_test_… only.",
                file=sys.stderr,
            )
            sys.exit(1)
        print("--- Step 1: Ingest (Stripe → cache) ---")
        ingest(output_path=args.cache)
    else:
        print(f"--- Step 1: Skip ingest (reusing {args.cache}) ---")

    print("\n--- Step 2: Naive sum (gross only) ---")
    try:
        gross = sum_gross_only(args.cache)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    if gross <= 0:
        print("No charge gross to post — nothing to do.", file=sys.stderr)
        sys.exit(1)

    print("\n--- Step 3: Naive Journal Entry ---")
    env = load_naive_env()
    body = build_naive_je_body(gross, env)

    if args.post:
        post_naive_journal_entry(gross)
        print("\nDone (INTENTIONALLY WRONG JE posted). For After: python main.py")
    else:
        print_naive_payload(body)
        print(
            "\nDry-run only — nothing posted. "
            "Re-run with --post to create this WRONG JE in sandbox.\n"
            "Correct After path: python main.py"
        )


if __name__ == "__main__":
    main()
