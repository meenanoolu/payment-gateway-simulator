"""
Rule-based fraud screening, run before a payment is authorized.

Three independent checks, cheapest/fastest first (fail fast):
  1. Blacklist       - known-bad card fingerprint, instant reject.
  2. Velocity        - same card used too many times in a short window
                        (classic card-testing / stolen-card pattern).
  3. Amount ceiling   - single transaction above a configured limit.

Each check returns as soon as one rule flags, and we always report the
reason so it's debuggable instead of a silent decline.
"""

from datetime import datetime, timedelta

from app.models import Transaction

BLACKLISTED_FINGERPRINTS = set()  # populated by an admin/incident process in a real system

VELOCITY_WINDOW_SECONDS = 60
VELOCITY_MAX_TXNS = 3

SINGLE_TXN_LIMIT = 5000


def is_blacklisted(fingerprint: str) -> bool:
    return fingerprint in BLACKLISTED_FINGERPRINTS


def check_velocity(fingerprint: str, db) -> bool:
    window_start = datetime.utcnow() - timedelta(seconds=VELOCITY_WINDOW_SECONDS)
    count = (
        db.query(Transaction)
        .filter(
            Transaction.card_fingerprint == fingerprint,
            Transaction.created_at >= window_start,
        )
        .count()
    )
    return count >= VELOCITY_MAX_TXNS


def evaluate(fingerprint: str, amount: float, db) -> dict:
    if is_blacklisted(fingerprint):
        return {"flagged": True, "reason": "Card is blacklisted"}
    if check_velocity(fingerprint, db):
        return {"flagged": True, "reason": "Velocity limit exceeded (too many attempts)"}
    if amount > SINGLE_TXN_LIMIT:
        return {"flagged": True, "reason": "Amount exceeds single-transaction limit"}
    return {"flagged": False, "reason": None}