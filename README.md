# Payment Gateway Simulator

A FastAPI service that simulates the core lifecycle of a card payment
gateway: authorize -> capture -> refund, with tokenization and rule-based
fraud screening in front of it. Built to understand how systems like
Stripe/Razorpay/Braintree are structured internally, not to process real
money — there's no real bank, real card network, or real PCI scope here.

## Why this shape

Payments are a two-phase commit in disguise. You don't want to take
someone's money the instant they click "buy" — you want to *reserve* it
(authorize), confirm the order is real, and only then *move* it
(capture). That's why `authorize` and `capture` are separate endpoints
instead of one `pay` endpoint, and it's the single design decision
everything else in this repo hangs off of.

## API

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/authorize` | Luhn check → tokenize card → fraud screen → `AUTHORIZED` / `DECLINED` |
| `POST` | `/capture/{transaction_id}` | `AUTHORIZED` → `CAPTURED` (money actually moves), full or partial |
| `POST` | `/void/{transaction_id}` | `AUTHORIZED` → `VOIDED` (release the hold, never captured) |
| `POST` | `/refund/{transaction_id}` | `CAPTURED` → `REFUNDED` / `PARTIALLY_REFUNDED` |
| `GET` | `/transactions/{transaction_id}` | Current state of one transaction |
| `GET` | `/analytics/summary` | Counts, totals, decline rate across all transactions |

Interactive docs at `/docs` once the server is running.

## State machine

```
              authorize
                 |
                 v
            AUTHORIZED  ----void----> VOIDED
                 |
              capture
                 |
                 v
             CAPTURED  ----refund(full)----> REFUNDED
                 |
           refund(partial)
                 |
                 v
        PARTIALLY_REFUNDED --refund--> REFUNDED / PARTIALLY_REFUNDED
```

Any call that doesn't match the transaction's current state (e.g.
capturing something already voided) returns `{"status": "ERROR", ...}`
with a reason, instead of silently corrupting the record.

## Project structure

```
app/
├── main.py             # HTTP layer only — routes validate + delegate, no business logic
├── payment_service.py  # The state machine: authorize/capture/void/refund, Luhn validation
├── token_service.py    # Card tokenization + one-way fingerprinting
├── fraud_service.py    # Blacklist / velocity / amount-ceiling checks
├── analytics.py        # Read-only reporting, kept separate from the write path
├── models.py            # Transaction row — refunds link back via parent_id
├── database.py          # SQLite engine/session setup
└── schemas.py            # Pydantic request models
tests/
├── test_authorize.py
├── test_capture.py
└── test_refund.py
```

## Design decisions and why

**Never store the raw card number.**
`token_service.py` immediately converts the PAN into a token, a `last4`
for display, and a SHA-256 fingerprint. The fingerprint is one-way — you
can't recover the card number from it — but the same card always
produces the same fingerprint, which is exactly what `fraud_service.py`
needs to spot "this card was just used 5 times in 30 seconds" without
ever holding onto the actual number. This mirrors PCI-DSS scope
reduction: the less of the system that ever sees a real PAN, the less
of it that has to be audited and secured.

**Idempotency keys on `/authorize`.**
Networks fail. If a client's request times out after the server already
processed it, a naive retry double-charges the card. Passing an
`idempotency_key` lets the server recognize "I've seen this exact
request before" and return the original result instead of creating a
second transaction. This is the same mechanism Stripe's API uses.

**Refunds create a new row instead of overwriting the original.**
`refund_payment` inserts a new `Transaction` with `parent_id` pointing
at the captured transaction, rather than just flipping a status field.
That gives a full audit trail — you can always answer "which refund(s)
came from which capture, and when" — which matters a lot for financial
reconciliation.

**Fraud checks run cheapest-first.**
Blacklist lookup (dict/set, O(1)) before velocity check (a DB query)
before the amount ceiling (already in memory). Fail fast on the check
that's fastest to evaluate.

## Difficulties hit while building this, and how they were resolved

1. **In-memory SQLite in tests silently returned "no such table."**
   Each new pooled connection to `sqlite:///:memory:` gets its *own*
   blank database — the table created via `Base.metadata.create_all()`
   on one connection isn't visible on another. Fixed by forcing
   SQLAlchemy's `StaticPool` in the test fixture so all test code shares
   one physical connection to the same in-memory DB.

2. **Deciding where "authorize vs. capture" split belongs.**
   Early version had a single `/authorize` that also wrote a final
   status. That collapses two real-world concepts (reserving funds vs.
   moving funds) into one, which makes partial capture and later void
   impossible to express cleanly. Solved by making capture and void
   both operate only on `AUTHORIZED` transactions, and refund only on
   `CAPTURED`/`PARTIALLY_REFUNDED` ones — the state machine *is* the
   fix.

3. **Partial refunds mutating the wrong record.**
   First attempt decremented `amount` on the original transaction
   directly and called it done, which loses the record of the refund
   itself. Fixed by giving refunds their own row (`status=REFUNDED`,
   `parent_id=<original id>`), and only adjusting the original's
   `amount`/`status` to reflect what's *left* after the refund.

4. **Fraud velocity check needing a time window without a live clock in
   tests.** Since `check_velocity` filters on `created_at >= now - 60s`,
   tests just insert transactions back-to-back in a real (fast) test
   run — all well within the window — rather than mocking time, keeping
   the test simple.

## What's still out of scope (intentionally)

- No real bank/card-network integration — this is a simulator.
- No authentication/API keys on the endpoints themselves.
- No currency conversion or multi-currency ledger correctness.
- Fraud rules are simple thresholds, not a trained model — that's a
  believable v2, not a v1 requirement.

## Tech stack

FastAPI · SQLAlchemy · Pydantic · SQLite · pytest

## Running it

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Interactive API docs at `http://localhost:8000/docs`.

## Running tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

16 tests cover authorization (Luhn validation, fraud declines, idempotent
replay), capture (full/partial, invalid states, invalid amounts), and
refunds (full/partial, double-refund handling, invalid states).

## Possible extensions

**Correctness / production-readiness**
- Swap `Float` for `Decimal`/integer minor-units for amounts — floats
  are a real bug source in financial systems (0.1 + 0.2 problem).
- Move off SQLite to Postgres and add row-level locking around
  capture/refund to prevent race conditions on concurrent requests
  against the same transaction.
- Add a real event/audit log table separate from `Transaction`, so state
  changes are append-only and replayable, not just inferable from rows.
- API key / auth layer on the endpoints (this is currently wide open).

**Fraud & risk**
- Replace the fixed velocity window with a sliding/rolling window or a
  token-bucket rate limiter per fingerprint.
- Add a risk *score* (weighted combination of checks) instead of binary
  flag/no-flag, so declines aren't all-or-nothing.
- 3D Secure–style step-up: instead of outright declining a borderline
  transaction, return a "requires verification" status.

**API & integration surface**
- Webhooks on state transitions (`payment.captured`, `payment.refunded`)
  with retry/backoff, mirroring how Stripe notifies merchants.
- A `/void` reason code and `/refund` reason code, since real gateways
  track *why* something was reversed for dispute handling later.
- Pagination + filtering on a `/transactions` list endpoint (currently
  only single-transaction lookup exists).

**Observability**
- Structured logging with a request/correlation ID threaded through
  authorize → capture → refund for a given transaction chain.
- Expand `/analytics/summary` into time-bucketed metrics (daily decline
  rate, capture latency) instead of all-time totals only.

**Testing**
- Property-based tests (Hypothesis) for the state machine — assert no
  sequence of calls can ever move a transaction to an invalid state.
- Concurrency tests that fire simultaneous captures/refunds at the same
  transaction ID to prove idempotency and locking actually hold.
