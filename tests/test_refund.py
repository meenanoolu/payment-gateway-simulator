from tests.conftest import VALID_CARD


def _authorize_and_capture(client, amount=100):
    txn_id = client.post(
        "/authorize", json={"card_number": VALID_CARD, "amount": amount}
    ).json()["transaction_id"]
    client.post(f"/capture/{txn_id}", json={})
    return txn_id


def test_full_refund_succeeds(client):
    txn_id = _authorize_and_capture(client, 100)
    resp = client.post(f"/refund/{txn_id}", json={})
    body = resp.json()
    assert body["status"] == "REFUNDED"
    assert body["amount"] == 100


def test_partial_refund_then_full_refund_of_remainder(client):
    txn_id = _authorize_and_capture(client, 100)
    first = client.post(f"/refund/{txn_id}", json={"amount": 40}).json()
    assert first["status"] == "REFUNDED"
    assert first["amount"] == 40

    remainder = client.get(f"/transactions/{txn_id}").json()
    assert remainder["status"] == "PARTIALLY_REFUNDED"
    assert remainder["amount"] == 60

    second = client.post(f"/refund/{txn_id}", json={"amount": 60}).json()
    assert second["amount"] == 60

    final = client.get(f"/transactions/{txn_id}").json()
    assert final["status"] == "REFUNDED"



def test_refund_more_than_captured_fails(client):
    txn_id = _authorize_and_capture(client, 100)
    resp = client.post(f"/refund/{txn_id}", json={"amount": 500})
    assert resp.json()["status"] == "ERROR"


def test_refund_uncaptured_authorization_fails(client):
    txn_id = client.post(
        "/authorize", json={"card_number": VALID_CARD, "amount": 100}
    ).json()["transaction_id"]
    resp = client.post(f"/refund/{txn_id}", json={})
    assert resp.json()["status"] == "ERROR"