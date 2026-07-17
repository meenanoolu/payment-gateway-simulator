from tests.conftest import INVALID_CARD, VALID_CARD


def test_authorize_valid_card_succeeds(client):
    resp = client.post("/authorize", json={"card_number": VALID_CARD, "amount": 100})
    body = resp.json()
    assert resp.status_code == 200
    assert body["status"] == "AUTHORIZED"
    assert "transaction_id" in body


def test_authorize_invalid_card_fails_luhn(client):
    resp = client.post("/authorize", json={"card_number": INVALID_CARD, "amount": 100})
    body = resp.json()
    assert body["status"] == "INVALID_CARD"



def test_authorize_amount_over_limit_is_declined(client):
    resp = client.post("/authorize", json={"card_number": VALID_CARD, "amount": 9999})
    body = resp.json()
    assert body["status"] == "DECLINED"
    assert "limit" in body["reason"].lower()


def test_authorize_velocity_limit_triggers_after_repeated_use(client):
    # Same card, 3 quick authorizations under the limit should succeed,
    # the 4th within the velocity window should be declined.
    for _ in range(3):
        resp = client.post("/authorize", json={"card_number": VALID_CARD, "amount": 50})
        assert resp.json()["status"] == "AUTHORIZED"

    resp = client.post("/authorize", json={"card_number": VALID_CARD, "amount": 50})
    assert resp.json()["status"] == "DECLINED"
    assert "velocity" in resp.json()["reason"].lower()


def test_idempotency_key_prevents_double_authorization(client):
    key = "req-abc-123"
    first = client.post(
        "/authorize", json={"card_number": VALID_CARD, "amount": 200, "idempotency_key": key}
    ).json()
    second = client.post(
        "/authorize", json={"card_number": VALID_CARD, "amount": 200, "idempotency_key": key}
    ).json()

    assert first["transaction_id"] == second["transaction_id"]
    assert second.get("idempotent_replay") is True