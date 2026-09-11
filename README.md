# Payment Gateway Simulator

A FastAPI service that simulates a real payment gateway's core lifecycle - authorize, capture, void, and refund - with the same separation of concerns real gateways (Stripe, Razorpay) use.

## What it does

- **Authorize**: validates a card (Luhn check), runs fraud screening, and reserves funds without moving money — mirrors how a checkout flow places a hold before an order ships.
- **Capture**: actually moves the money on a previously authorized transaction, full or partial.
- **Void**: cancels an authorized-but-not-yet-captured transaction.
- **Refund**: reverses a captured transaction, full or partial, and preserves a full audit trail (a refund is a *new* linked row, not an overwrite).
- **Analytics**: a read-only summary endpoint (transaction counts by status, total authorized/refunded value, decline rate).

## State machine

```
INITIATED (implicit) --authorize--> AUTHORIZED
AUTHORIZED --capture--> CAPTURED
AUTHORIZED --void--> VOIDED
CAPTURED --refund (full)--> REFUNDED
CAPTURED --refund (partial)--> PARTIALLY_REFUNDED
PARTIALLY_REFUNDED --refund--> REFUNDED / PARTIALLY_REFUNDED
```
Any call that doesn't match the current state returns a structured error instead of silently doing the wrong thing.

## Design decisions worth knowing about

- **Card tokenization**: the raw card number never touches storage or logs after the first request — only a token, last 4 digits, and a one-way fingerprint (SHA-256 hash) are kept. Same card always produces the same fingerprint, without being reversible back to the number — this is what powers fraud velocity checks without ever storing the PAN, the same scope-reduction principle real gateways use for PCI-DSS.
- **Idempotency keys**: retrying the same request (e.g. after a client-side timeout) with the same idempotency key returns the original result instead of double-charging the card.
- **Fraud screening** runs three checks before authorization, cheapest first: blacklist lookup, velocity check (same card used 3+ times in 60 seconds), and a single-transaction amount ceiling.
- **HTTP layer is thin**: `main.py` only validates request shape and delegates to `payment_service.py`. Business logic returns plain dicts with a `status` key rather than raising HTTP exceptions directly, which keeps it testable independent of FastAPI.

## Tech stack

FastAPI · SQLAlchemy · Pydantic · SQLite · pytest/httpx (for testing)

## Project structure

```
app/
├── main.py              # HTTP routes only, no business logic
├── payment_service.py   # Core state machine: authorize/capture/void/refund
├── fraud_service.py      # Blacklist, velocity, and amount-limit checks
├── token_service.py      # Card tokenization (token/last4/fingerprint)
├── analytics.py          # Read-only reporting over transactions
├── models.py             # SQLAlchemy Transaction model
├── schemas.py             # Pydantic request schemas
└── database.py            # SQLite engine/session setup
```

## Running it locally

```bash
git clone https://github.com/meenanoolu/payment-gateway-simulator.git
cd payment-gateway-simulator
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API docs (Swagger UI) available at `http://localhost:8000/docs` once running.

## Example: full payment lifecycle

```bash
# Authorize
curl -X POST localhost:8000/authorize \
  -H "Content-Type: application/json" \
  -d '{"card_number": "4242424242424242", "amount": 500}'

# Capture (using the transaction_id returned above)
curl -X POST localhost:8000/capture/1

# Refund
curl -X POST localhost:8000/refund/1 -d '{"amount": 200}'

# Check analytics
curl localhost:8000/analytics/summary
```

## Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/authorize` | Validate a card and reserve funds |
| POST | `/capture/{transaction_id}` | Move funds on an authorized transaction |
| POST | `/void/{transaction_id}` | Cancel an authorized (uncaptured) transaction |
| POST | `/refund/{transaction_id}` | Refund a captured transaction, full or partial |
| GET | `/transactions/{transaction_id}` | Look up a transaction |
| GET | `/analytics/summary` | Aggregate stats across all transactions |