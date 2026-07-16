"""
Core payment lifecycle: authorize -> capture -> refund, with void as a
side branch off authorize. This mirrors how Stripe/Razorpay/most real
gateways separate "authorize" (reserve funds, don't move money yet) from
"capture" (actually move the money) -- it's what lets a checkout flow
place a hold, then only capture once the order actually ships.

State machine enforced here:

    INITIATED (implicit) --authorize-->  AUTHORIZED
    AUTHORIZED --capture-->  CAPTURED
    AUTHORIZED --void-->     VOIDED
    CAPTURED --refund(full)-->        REFUNDED
    CAPTURED --refund(partial)-->     PARTIALLY_REFUNDED
    PARTIALLY_REFUNDED --refund-->    REFUNDED / PARTIALLY_REFUNDED (again)

Any call that doesn't match the current state returns an ERROR with a
reason instead of silently doing the wrong thing.
"""

from app.fraud_service import evaluate
from app.models import Transaction
from app.token_service import tokenize_card


def validate_card(card: str) -> bool:
    """Luhn checksum -- catches typos and obviously fake card numbers.
    This is NOT fraud detection; it's basic input validation."""
    if not card.isdigit():
        return False
    digits = [int(x) for x in card]
    checksum = 0
    reverse = digits[::-1]
    for i, digit in enumerate(reverse):
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def _get_txn(transaction_id: int, db):
    return db.query(Transaction).filter(Transaction.id == transaction_id).first()


def authorize_payment(card_number: str, amount: float, db, idempotency_key: str = None) -> dict:
    # Idempotency: if a client retries the same request (e.g. after a
    # network timeout) with the same key, return the original result
    # instead of double-charging the card.
    if idempotency_key:
        existing = db.query(Transaction).filter(
            Transaction.idempotency_key == idempotency_key
        ).first()
        if existing:
            return {
                "status": existing.status,
                "transaction_id": existing.id,
                "card_last4": existing.card_last4,
                "idempotent_replay": True,
            }

    if not validate_card(card_number):
        return {"status": "INVALID_CARD", "reason": "Luhn check failed"}

    token_info = tokenize_card(card_number)
    fraud_result = evaluate(token_info["fingerprint"], amount, db)

    if fraud_result["flagged"]:
        txn = Transaction(
            card_token=token_info["token"],
            card_last4=token_info["last4"],
            card_fingerprint=token_info["fingerprint"],
            amount=amount,
            status="DECLINED",
            idempotency_key=idempotency_key,
        )
        db.add(txn)
        db.commit()
        db.refresh(txn)
        return {"status": "DECLINED", "reason": fraud_result["reason"], "transaction_id": txn.id}

    txn = Transaction(
        card_token=token_info["token"],
        card_last4=token_info["last4"],
        card_fingerprint=token_info["fingerprint"],
        amount=amount,
        status="AUTHORIZED",
        idempotency_key=idempotency_key,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return {"status": "AUTHORIZED", "transaction_id": txn.id, "card_last4": txn.card_last4}


def capture_payment(transaction_id: int, db, amount: float = None) -> dict:
    txn = _get_txn(transaction_id, db)
    if not txn:
        return {"status": "ERROR", "reason": "Transaction not found"}
    if txn.status != "AUTHORIZED":
        return {"status": "ERROR", "reason": f"Cannot capture from state {txn.status}"}

    capture_amount = amount if amount is not None else txn.amount
    if capture_amount <= 0 or capture_amount > txn.amount:
        return {"status": "ERROR", "reason": "Invalid capture amount"}

    txn.status = "CAPTURED"
    txn.amount = capture_amount
    db.commit()
    db.refresh(txn)
    return {"status": "CAPTURED", "transaction_id": txn.id, "amount": txn.amount}


def void_payment(transaction_id: int, db) -> dict:
    txn = _get_txn(transaction_id, db)
    if not txn:
        return {"status": "ERROR", "reason": "Transaction not found"}
    if txn.status != "AUTHORIZED":
        return {"status": "ERROR", "reason": f"Cannot void from state {txn.status}"}

    txn.status = "VOIDED"
    db.commit()
    db.refresh(txn)
    return {"status": "VOIDED", "transaction_id": txn.id}


def refund_payment(transaction_id: int, db, amount: float = None) -> dict:
    txn = _get_txn(transaction_id, db)
    if not txn:
        return {"status": "ERROR", "reason": "Transaction not found"}
    if txn.status not in ("CAPTURED", "PARTIALLY_REFUNDED"):
        return {"status": "ERROR", "reason": f"Cannot refund from state {txn.status}"}

    refund_amount = amount if amount is not None else txn.amount
    if refund_amount <= 0 or refund_amount > txn.amount:
        return {"status": "ERROR", "reason": "Invalid refund amount"}

    refund_txn = Transaction(
        card_token=txn.card_token,
        card_last4=txn.card_last4,
        card_fingerprint=txn.card_fingerprint,
        amount=refund_amount,
        status="REFUNDED",
        parent_id=txn.id,
    )
    db.add(refund_txn)

    if refund_amount == txn.amount:
        txn.status = "REFUNDED"
    else:
        txn.status = "PARTIALLY_REFUNDED"
        txn.amount -= refund_amount

    db.commit()
    db.refresh(refund_txn)
    return {
        "status": "REFUNDED",
        "refund_transaction_id": refund_txn.id,
        "original_transaction_id": txn.id,
        "amount": refund_amount,
    }