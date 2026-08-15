from decimal import Decimal

from receipt_sender import ReceiptRequest, send_work_order_receipt


class RecordingClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def send(self, **request: str) -> dict[str, str]:
        self.calls.append(request)
        return {"message_id": "msg_123"}


def make_receipt(status: str) -> ReceiptRequest:
    return ReceiptRequest(
        work_order_id="WO-1042",
        customer_email="customer@example.com",
        customer_name="Riley Chen",
        dispatch_status=status,  # type: ignore[arg-type]
        amount=Decimal("189.50"),
        currency="USD",
        technician_name="Morgan Lee",
    )


def test_receipt_is_held_until_dispatch_is_completed() -> None:
    client = RecordingClient()

    result = send_work_order_receipt(make_receipt("on_site"), client)  # type: ignore[arg-type]

    assert result.outcome == "skipped"
    assert result.reason == "receipt waits for a completed work order"
    assert client.calls == []


def test_completed_order_sends_once_with_stable_idempotency_key() -> None:
    client = RecordingClient()

    result = send_work_order_receipt(make_receipt("completed"), client)  # type: ignore[arg-type]

    assert result.message_id == "msg_123"
    assert client.calls[0]["idempotency_key"] == "work-order-receipt:WO-1042"
    assert "189.50 USD" in client.calls[0]["html_body"]
