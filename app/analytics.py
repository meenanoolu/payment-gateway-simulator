"""
Read-only reporting over the transactions table.

Kept deliberately separate from payment_service.py: analytics is a
side-consumer of the data, not part of the write path. If this grew into
a real system, this module is exactly the seam where you'd peel off a
read replica or a separate reporting service without touching the
payment logic at all.
"""

from sqlalchemy import func

from app.models import Transaction


def summary(db) -> dict:
    total_txns = db.query(Transaction).count()

    by_status_rows = (
        db.query(Transaction.status, func.count(Transaction.id))
        .group_by(Transaction.status)
        .all()
    )
    by_status = {status: count for status, count in by_status_rows}

    total_authorized_value = (
        db.query(func.sum(Transaction.amount))
        .filter(Transaction.status.in_(["AUTHORIZED", "CAPTURED", "PARTIALLY_REFUNDED"]))
        .scalar()
        or 0
    )
    total_refunded_value = (
        db.query(func.sum(Transaction.amount))
        .filter(Transaction.status == "REFUNDED")
        .scalar()
        or 0
    )

    declined = by_status.get("DECLINED", 0) + by_status.get("INVALID_CARD", 0)
    decline_rate = round(declined / total_txns, 4) if total_txns else 0.0

    return {
        "total_transactions": total_txns,
        "by_status": by_status,
        "total_authorized_value": total_authorized_value,
        "total_refunded_value": total_refunded_value,
        "decline_rate": decline_rate,
    }