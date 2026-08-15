from __future__ import annotations

from decimal import Decimal
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr, Field

from receipt_sender import (
    InfraiEmailClient,
    InfraiError,
    ReceiptRequest,
    TechnicianFollowUp,
    WorkOrderPhoto,
    send_work_order_receipt,
)


class PhotoInput(BaseModel):
    caption: str = Field(min_length=1)
    url: str = Field(pattern=r"^https://")


class FollowUpInput(BaseModel):
    needed: bool
    note: str | None = None


class WorkOrderReceiptInput(BaseModel):
    work_order_id: str = Field(min_length=1)
    customer_email: EmailStr
    customer_name: str = Field(min_length=1)
    dispatch_status: Literal[
        "scheduled", "en_route", "on_site", "completed", "cancelled"
    ]
    amount: Decimal = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    technician_name: str = Field(min_length=1)
    photos: list[PhotoInput] = []
    follow_up: FollowUpInput = FollowUpInput(needed=False)


class ReceiptResponse(BaseModel):
    outcome: Literal["sent", "skipped"]
    message_id: str | None
    reason: str | None


app = FastAPI(title="Field service receipt sender")


@app.post("/work-orders/receipt", response_model=ReceiptResponse)
def create_receipt(body: WorkOrderReceiptInput) -> ReceiptResponse:
    receipt = ReceiptRequest(
        work_order_id=body.work_order_id,
        customer_email=str(body.customer_email),
        customer_name=body.customer_name,
        dispatch_status=body.dispatch_status,
        amount=body.amount,
        currency=body.currency,
        technician_name=body.technician_name,
        photos=tuple(WorkOrderPhoto(**photo.model_dump()) for photo in body.photos),
        follow_up=TechnicianFollowUp(**body.follow_up.model_dump()),
    )
    try:
        result = send_work_order_receipt(receipt, InfraiEmailClient.from_environment())
    except InfraiError as exc:
        caller_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=caller_status, detail=exc.details) from exc
    return ReceiptResponse(
        outcome=result.outcome,
        message_id=result.message_id,
        reason=result.reason,
    )
