from app.models import Transaction
from app.database import SessionLocal

def validate_card(card):
    digits = [int(x) for x in card]
    checksum = 0
    reverse = digits[::-1]
    for i, digit in enumerate(reverse):
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0

def authorize_payment(card_number: str, amount: float, db):
    if not validate_card(card_number):
        return {"status": "INVALID_CARD", "reason": "Luhn check failed"}
    if amount > 5000:
        return {"status": "DECLINED", "reason": "Amount exceeds limit"}
    
    txn = Transaction(card_number=card_number, amount=amount, status="AUTHORIZED")
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return {"status": "AUTHORIZED", "transaction_id": txn.id}