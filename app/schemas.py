from pydantic import BaseModel

class PaymentRequest(BaseModel):
    card_number:str
    aount:float
    