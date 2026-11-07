"""
Phase 1 — Stage the clearing timing problem (Before beat).

Creates Stripe test-mode PaymentIntents/charges with processing fees and leaves
a subset of balance transactions without a payout link (payout=null) so the
demo shows mid-cycle uncleared variance. Does not call QuickBooks.
"""

from __future__ import annotations

import os
import sys

import stripe
from dotenv import load_dotenv

# Amounts in cents — mix of sizes for a readable Before narration.
CHARGE_AMOUNTS_CENTS = [4500, 8200, 12500, 2999, 6700]


def _require_stripe_key() -> str:
    load_dotenv()
    key = os.getenv("STRIPE_TEST_SECRET_KEY", "").strip()
    if not key or key.startswith("sk_test_REPLACE"):
        print(
            "Missing STRIPE_TEST_SECRET_KEY. Set a real Stripe test secret in .env.",
            file=sys.stderr,
        )
        sys.exit(1)
    if key.startswith("sk_live_"):
        print("Refusing live Stripe key. Use a sk_test_… key only.", file=sys.stderr)
        sys.exit(1)
    return key


def _create_succeeded_intent(amount_cents: int, index: int) -> stripe.PaymentIntent:
    """Confirm a test PaymentIntent so a Charge + BalanceTransaction (+ fee) exist."""
    return stripe.PaymentIntent.create(
        amount=amount_cents,
        currency="usd",
        payment_method="pm_card_visa",
        confirm=True,
        automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
        description=f"Demo charge #{index + 1} — clearing variance seed",
        metadata={"demo": "stripe-qbo-clearing", "seed_index": str(index)},
    )


def _balance_txn_for_charge(charge_id: str) -> stripe.BalanceTransaction | None:
    charge = stripe.Charge.retrieve(charge_id)
    bt_id = charge.balance_transaction
    if not bt_id:
        return None
    return stripe.BalanceTransaction.retrieve(bt_id)


def main() -> None:
    stripe.api_key = _require_stripe_key()

    print("=== Stripe seed (Before) - test charges with fees ===\n")

    created: list[dict] = []
    for i, amount in enumerate(CHARGE_AMOUNTS_CENTS):
        intent = _create_succeeded_intent(amount, i)
        charge_id = intent.latest_charge
        if isinstance(charge_id, stripe.Charge):
            charge_id = charge_id.id

        bt = _balance_txn_for_charge(charge_id) if charge_id else None
        payout = getattr(bt, "payout", None) if bt else None
        if isinstance(payout, stripe.Payout):
            payout = payout.id

        row = {
            "payment_intent": intent.id,
            "charge": charge_id,
            "balance_transaction": bt.id if bt else None,
            "amount_cents": bt.amount if bt else amount,
            "fee_cents": bt.fee if bt else None,
            "net_cents": bt.net if bt else None,
            "payout": payout,
        }
        created.append(row)
        print(
            f"[{i + 1}/{len(CHARGE_AMOUNTS_CENTS)}] "
            f"PI={row['payment_intent']}  ch={row['charge']}  "
            f"txn={row['balance_transaction']}  "
            f"gross={row['amount_cents']} fee={row['fee_cents']} net={row['net_cents']}  "
            f"payout={row['payout']!r}"
        )

    uncleared = [r for r in created if r["payout"] is None]
    print("\n--- Summary ---")
    print(f"Created PaymentIntents: {len(created)}")
    print(f"BalanceTransactions with payout=null (uncleared): {len(uncleared)}")
    if uncleared:
        print("Uncleared txn IDs (mid-cycle timing variance for the demo):")
        for r in uncleared:
            print(f"  {r['balance_transaction']}  net_cents={r['net_cents']}")
    else:
        print(
            "Note: all seeded txns already have a payout. "
            "Disable automatic payouts in the Stripe Dashboard (or wait for a "
            "fresh test account) so new charges stay payout=null for the Before beat."
        )
    print("\nSeed complete. No QBO calls were made. Next: python main.py")


if __name__ == "__main__":
    main()
