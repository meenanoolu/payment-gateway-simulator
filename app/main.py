from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {
        "message": "Payment Gateway Simulator"
    }

@app.get("/health")
def health():
    return {
        "status": "running"
    }