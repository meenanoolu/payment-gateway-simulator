from fastapi import FastAPI

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

    return {
        "status":"AUTHORIZED"
    }