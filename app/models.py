from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from app.database import Base


class Transaction(Base):
    """
    One row = one state in the payment lifecycle.
    Authorize creates a row. Capture/Void/Refund either update that row
    or (for refunds) create a new linked row pointing back via parent_id.
    This keeps a full audit trail instead of overwriting history.
    """
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)

    # We never store the raw card number. Only a token + last 4 + a
    # one-way fingerprint (for fraud velocity checks on repeat cards).
    card_token = Column(String, index=True)
    card_last4 = Column(String)
    card_fingerprint = Column(String, index=True)

    amount = Column(Float)
    currency = Column(String, default="INR")

    # INITIATED -> AUTHORIZED -> CAPTURED -> REFUNDED / PARTIALLY_REFUNDED
    #                        \-> VOIDED
    #           -> DECLINED / INVALID_CARD
    status = Column(String, default="INITIATED")

    parent_id = Column(Integer, nullable=True)  # links a refund to its capture
    idempotency_key = Column(String, unique=True, nullable=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)