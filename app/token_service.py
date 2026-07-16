"""
Card tokenization.

Real gateways never let the raw PAN (card number) touch application logs,
databases, or downstream services after the first hop -- that's the core
of PCI-DSS scope reduction. We simulate that boundary here:

- token        : a random opaque reference other services can pass around
                 instead of the real card number (like Stripe's tok_xxx).
- last4        : safe to display to users/support ("card ending 4242").
- fingerprint  : a one-way hash of the PAN. Same card -> same fingerprint,
                 every time, but you can't reverse it back to the card
                 number. Used by fraud_service to spot the same card
                 being reused rapidly, without ever storing the PAN.
"""

import hashlib
import uuid


def tokenize_card(card_number: str) -> dict:
    card_number = card_number.strip()
    token = "tok_" + uuid.uuid4().hex[:16]
    last4 = card_number[-4:]
    fingerprint = hashlib.sha256(card_number.encode()).hexdigest()
    return {"token": token, "last4": last4, "fingerprint": fingerprint}