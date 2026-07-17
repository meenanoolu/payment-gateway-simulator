from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from app.analytics import summary
from app.database import SessionLocal, engine
from app.models import Base, Transaction
from app.payment_service import authorize_payment, capture_payment, refund_payment, void_payment
from app.schemas import CaptureRequest, PaymentRequest, RefundRequest

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Payment Gateway Simulator")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
def home():
    return {"message": "Payment Gateway Simulator"}


@app.post("/authorize")
def authorize(payment: PaymentRequest, db: Session = Depends(get_db)):
    return authorize_payment(
        payment.card_number, payment.amount, db, idempotency_key=payment.idempotency_key
    )


@app.post("/capture/{transaction_id}")
def capture(transaction_id: int, body: CaptureRequest = CaptureRequest(), db: Session = Depends(get_db)):
    return capture_payment(transaction_id, db, amount=body.amount)


@app.post("/void/{transaction_id}")
def void(transaction_id: int, db: Session = Depends(get_db)):
    return void_payment(transaction_id, db)


@app.post("/refund/{transaction_id}")
def refund(transaction_id: int, body: RefundRequest = RefundRequest(), db: Session = Depends(get_db)):
    return refund_payment(transaction_id, db, amount=body.amount)



@app.get("/transactions/{transaction_id}")
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


@app.get("/analytics/summary")
def analytics_summary(db: Session = Depends(get_db)):
    return summary(db)