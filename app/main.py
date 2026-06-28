from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from app.database import engine, SessionLocal
from app.models import Base
from app.schemas import PaymentRequest
from app.payment_service import authorize_payment

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
    return authorize_payment(payment.card_number, payment.amount, db)