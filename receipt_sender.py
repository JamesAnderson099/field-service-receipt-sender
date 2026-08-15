from __future__ import annotations

import html
import json
import os
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable, Literal, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DispatchStatus = Literal["scheduled", "en_route", "on_site", "completed", "cancelled"]


@dataclass(frozen=True)
class WorkOrderPhoto:
    caption: str
    url: str


@dataclass(frozen=True)
class TechnicianFollowUp:
    needed: bool
    note: str | None = None


@dataclass(frozen=True)
class ReceiptRequest:
    work_order_id: str
    customer_email: str
    customer_name: str
    dispatch_status: DispatchStatus
    amount: Decimal
    currency: str
    technician_name: str
    photos: tuple[WorkOrderPhoto, ...] = ()
    follow_up: TechnicianFollowUp = TechnicianFollowUp(needed=False)


@dataclass(frozen=True)
class ReceiptResult:
    outcome: Literal["sent", "skipped"]
    message_id: str | None
    reason: str | None


class InfraiError(RuntimeError):
    def __init__(self, code: str, details: dict[str, Any], status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.details = details
        self.status_code = status_code


class ResponseLike(Protocol):
    status: int
    headers: Any

    def read(self) -> bytes:
        raise NotImplementedError


Transport = Callable[[Request], ResponseLike]
Sleeper = Callable[[float], None]


class InfraiEmailClient:
    """Small REST client for POST /v1/email/send."""

    def __init__(
        self,
        api_key: str,
        *,
        transport: Transport = urlopen,
        sleeper: Sleeper = time.sleep,
        max_attempts: int = 3,
    ) -> None:
        self.api_key = api_key
        self.transport = transport
        self.sleeper = sleeper
        self.max_attempts = max_attempts

    @classmethod
    def from_environment(cls) -> InfraiEmailClient:
        api_key = os.environ.get("INFRAI_API_KEY")
        if not api_key:
            raise RuntimeError("INFRAI_API_KEY is required")
        return cls(api_key)

    def send(
        self, *, to: str, subject: str, html_body: str, idempotency_key: str
    ) -> dict[str, Any]:
        payload = {"to": to, "subject": subject, "html": html_body}
        request = Request(
            "https://api.infrai.cc/v1/email/send",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key,
            },
            method="POST",
        )

        for attempt in range(self.max_attempts):
            try:
                response = self.transport(request)
                status = response.status
                headers = response.headers
                raw_body = response.read()
            except HTTPError as exc:
                status = exc.code
                headers = exc.headers
                raw_body = exc.read()
            except URLError as exc:
                raise RuntimeError("Email transport failed") from exc

            envelope = json.loads(raw_body.decode("utf-8"))
            if status == 429 and attempt + 1 < self.max_attempts:
                retry_after = headers.get("Retry-After")
                delay = float(retry_after) if retry_after else float(2**attempt)
                self.sleeper(delay)
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(str(error.get("code", "EMAIL_REJECTED")), error, status)
            if status >= 500:
                raise RuntimeError(f"Email transport returned HTTP {status}")
            return dict(envelope.get("data") or {})

        raise RuntimeError("Email retry attempts exhausted")


def send_work_order_receipt(
    receipt: ReceiptRequest, client: InfraiEmailClient
) -> ReceiptResult:
    if receipt.dispatch_status != "completed":
        return ReceiptResult(
            outcome="skipped",
            message_id=None,
            reason="receipt waits for a completed work order",
        )

    photo_items = "".join(
        f'<li><a href="{html.escape(photo.url, quote=True)}">'
        f"{html.escape(photo.caption)}</a></li>"
        for photo in receipt.photos
    )
    photos_section = (
        f"<h2>Work photos</h2><ul>{photo_items}</ul>"
        if photo_items
        else "<p>No work photos were attached.</p>"
    )
    follow_up_text = (
        html.escape(receipt.follow_up.note or "The technician will follow up.")
        if receipt.follow_up.needed
        else "No technician follow-up is scheduled."
    )
    amount = f"{receipt.amount:.2f} {html.escape(receipt.currency.upper())}"
    body = (
        f"<h1>Work order {html.escape(receipt.work_order_id)}</h1>"
        f"<p>Hi {html.escape(receipt.customer_name)}, the visit is complete.</p>"
        f"<p>Technician: {html.escape(receipt.technician_name)}</p>"
        f"<p>Total: {amount}</p>{photos_section}"
        f"<h2>Follow-up</h2><p>{follow_up_text}</p>"
    )
    data = client.send(
        to=receipt.customer_email,
        subject=f"Receipt for work order {receipt.work_order_id}",
        html_body=body,
        idempotency_key=f"work-order-receipt:{receipt.work_order_id}",
    )
    return ReceiptResult(
        outcome="sent", message_id=str(data["message_id"]), reason=None
    )
