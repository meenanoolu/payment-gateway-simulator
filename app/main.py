"""
HTTP layer only. Every route just validates the request shape (via the
Pydantic schemas) and hands off to payment_service / analytics. No
business logic lives here -- if you're tempted to add an if/else about
transaction state in this file, it belongs in payment_service.py instead.
"""

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.analytics import summary
from app.database import SessionLocal, engine
from app.models import Base, Transaction
from app.payment_service import authorize_payment, capture_payment, refund_payment, void_payment
from app.schemas import CaptureRequest, PaymentRequest, RefundRequest

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Payment Gateway Simulator",
    description="A simulated payment lifecycle: authorize, capture, void, and refund.",
    version="1.0.0",
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _respond(result: dict) -> JSONResponse:
    """
    payment_service functions always return a dict with a "status" key
    rather than raising exceptions -- that keeps the business logic
    testable without needing to catch HTTP-specific errors. This helper
    is the one place that translates those statuses into real HTTP codes,
    so callers of the API (not just people reading the JSON body) can
    tell success from failure.
    """
    status_code = 200
    if result.get("status") == "ERROR":
        status_code = 404 if "not found" in result.get("reason", "").lower() else 400
    elif result.get("status") in ("DECLINED", "INVALID_CARD"):
        status_code = 402  # Payment Required -- the semantically correct code for a declined charge
    return JSONResponse(content=result, status_code=status_code)


@app.get("/", tags=["Health"])
def home():
    return {"message": "Payment Gateway Simulator"}


@app.post("/authorize", tags=["Payments"], summary="Validate a card and reserve funds")
def authorize(payment: PaymentRequest, db: Session = Depends(get_db)):
    result = authorize_payment(
        payment.card_number, payment.amount, db, idempotency_key=payment.idempotency_key
    )
    return _respond(result)


@app.post("/capture/{transaction_id}", tags=["Payments"], summary="Move funds on an authorized transaction")
def capture(transaction_id: int, body: CaptureRequest = CaptureRequest(), db: Session = Depends(get_db)):
    result = capture_payment(transaction_id, db, amount=body.amount)
    return _respond(result)


@app.post("/void/{transaction_id}", tags=["Payments"], summary="Cancel an authorized (uncaptured) transaction")
def void(transaction_id: int, db: Session = Depends(get_db)):
    result = void_payment(transaction_id, db)
    return _respond(result)


@app.post("/refund/{transaction_id}", tags=["Payments"], summary="Refund a captured transaction, in full or in part")
def refund(transaction_id: int, body: RefundRequest = RefundRequest(), db: Session = Depends(get_db)):
    result = refund_payment(transaction_id, db, amount=body.amount)
    return _respond(result)


@app.get("/transactions/{transaction_id}", tags=["Transactions"])
def get_transaction(transaction_id: int, db: Session = Depends(get_db)):
    txn = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {
        "id": txn.id,
        "status": txn.status,
        "amount": txn.amount,
        "currency": txn.currency,
        "card_last4": txn.card_last4,
        "parent_id": txn.parent_id,
        "created_at": txn.created_at,
        "updated_at": txn.updated_at,
    }


@app.get("/analytics/summary", tags=["Analytics"])
def analytics_summary(db: Session = Depends(get_db)):
    return summary(db)