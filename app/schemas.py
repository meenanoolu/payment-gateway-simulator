from typing import Optional

from pydantic import BaseModel, Field


class PaymentRequest(BaseModel):
    card_number: str = Field(..., min_length=13, max_length=19)
    amount: float = Field(..., gt=0)
    idempotency_key: Optional[str] = None


class CaptureRequest(BaseModel):
    amount: Optional[float] = None


class RefundRequest(BaseModel):
    amount: Optional[float] = None