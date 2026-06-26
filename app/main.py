from fastapi import FastAPI
from app.payment_service import authorize_payment

app = FastAPI()

@app.get("/")
def home():
    return {
        "message":"Payment Gateway Simulator"
    }


from app.schemas import PaymentRequest
from database import engine
from models import Base

Base.metadata.create_all(bind=engine)

@app.post("/authorize")
def authorize(payment: PaymentRequest):

    return authorize_payment(
        payment.card_number, 
        payment.amount
    )

