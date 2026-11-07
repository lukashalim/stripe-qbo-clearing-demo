"""
Phase 2 / Step 3 — Refresh Intuit OAuth and POST a sandbox JournalEntry.
"""

from __future__ import annotations

import base64
import os
import sys
from typing import Any

import requests
from dotenv import load_dotenv

INTUIT_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
QBO_SANDBOX_BASE = "https://sandbox-quickbooks.api.intuit.com"

ACCOUNT_ENV_BY_BUCKET = {
    "checking": "CHECKING_ACCOUNT_ID",
    "fees": "MERCHANT_FEES_ACCOUNT_ID",
    "clearing": "STRIPE_CLEARING_ACCOUNT_ID",
    "sales": "SALES_REVENUE_ACCOUNT_ID",
}

REQUIRED_ENV = [
    "QBO_CLIENT_ID",
    "QBO_CLIENT_SECRET",
    "QBO_REFRESH_TOKEN",
    "QBO_REALM_ID",
    *ACCOUNT_ENV_BY_BUCKET.values(),
]


def _load_env() -> dict[str, str]:
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
            "Missing or placeholder QBO env vars:\n  - " + "\n  - ".join(missing),
            file=sys.stderr,
        )
        sys.exit(1)
    return values


def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    """OAuth2 refresh_token grant against Intuit's token endpoint."""
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    response = requests.post(
        INTUIT_TOKEN_URL,
        headers={
            "Authorization": f"Basic {basic}",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    if response.status_code >= 400:
        print(
            f"Intuit token refresh failed ({response.status_code}): {response.text}",
            file=sys.stderr,
        )
        sys.exit(1)

    payload = response.json()
    access_token = payload.get("access_token")
    if not access_token:
        print(f"Intuit token response missing access_token: {payload}", file=sys.stderr)
        sys.exit(1)
    return access_token


def _build_je_body(
    lines: list[dict[str, Any]], env: dict[str, str]
) -> dict[str, Any]:
    qbo_lines: list[dict[str, Any]] = []
    for line in lines:
        env_key = ACCOUNT_ENV_BY_BUCKET[line["bucket"]]
        account_id = env[env_key]
        qbo_lines.append(
            {
                "DetailType": "JournalEntryLineDetail",
                "Amount": line["amount"],
                "Description": line["description"],
                "JournalEntryLineDetail": {
                    "PostingType": line["posting_type"],
                    "AccountRef": {"value": account_id},
                },
            }
        )

    return {
        "DocNumber": "STRIPE-CLR",
        "PrivateNote": "Stripe clearing demo — automated JE from balance transactions",
        "Line": qbo_lines,
    }


def post_journal_entry(transform_result: dict[str, Any]) -> dict[str, Any]:
    """Refresh OAuth and POST the 4-line (or fewer if zeros skipped) sandbox JE."""
    env = _load_env()
    lines = transform_result.get("lines") or []
    if not lines:
        print("No journal lines to post (all aggregates were zero).", file=sys.stderr)
        sys.exit(1)

    access_token = refresh_access_token(
        env["QBO_CLIENT_ID"],
        env["QBO_CLIENT_SECRET"],
        env["QBO_REFRESH_TOKEN"],
    )

    realm = env["QBO_REALM_ID"]
    url = f"{QBO_SANDBOX_BASE}/v3/company/{realm}/journalentry"
    body = _build_je_body(lines, env)

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
    print("=== QBO Journal Entry posted ===")
    print(f"  Id:         {je.get('Id')}")
    print(f"  DocNumber:  {je.get('DocNumber')}")
    print(f"  SyncToken:  {je.get('SyncToken')}")
    print(f"  Lines:      {len(je.get('Line') or lines)}")
    return result


if __name__ == "__main__":
    print(
        "post_qbo.py expects a transform result from main.py / transform_engine.",
        file=sys.stderr,
    )
    sys.exit(1)
