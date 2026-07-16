from tests.conftest import VALID_CARD


def _authorize(client, amount=100):
    resp = client.post("/authorize", json={"card_number": VALID_CARD, "amount": amount})
    return resp.json()["transaction_id"]


def test_capture_full_amount_succeeds(client):
    txn_id = _authorize(client, 100)
    resp = client.post(f"/capture/{txn_id}", json={})
    body = resp.json()
    assert body["status"] == "CAPTURED"
    assert body["amount"] == 100


def test_capture_partial_amount_succeeds(client):
    txn_id = _authorize(client, 100)
    resp = client.post(f"/capture/{txn_id}", json={"amount": 60})
    body = resp.json()
    assert body["status"] == "CAPTURED"
    assert body["amount"] == 60


def test_capture_more_than_authorized_fails(client):
    txn_id = _authorize(client, 100)
    resp = client.post(f"/capture/{txn_id}", json={"amount": 150})
    assert resp.json()["status"] == "ERROR"


def test_capture_twice_fails(client):
    txn_id = _authorize(client, 100)
    client.post(f"/capture/{txn_id}", json={})
    resp = client.post(f"/capture/{txn_id}", json={})
    assert resp.json()["status"] == "ERROR"


def test_void_authorized_transaction_succeeds(client):
    txn_id = _authorize(client, 100)
    resp = client.post(f"/void/{txn_id}")
    assert resp.json()["status"] == "VOIDED"


def test_capture_after_void_fails(client):
    txn_id = _authorize(client, 100)
    client.post(f"/void/{txn_id}")
    resp = client.post(f"/capture/{txn_id}", json={})
    assert resp.json()["status"] == "ERROR"


def test_capture_nonexistent_transaction_fails(client):
    resp = client.post("/capture/99999", json={})
    assert resp.json()["status"] == "ERROR"