from decimal import Decimal

from receipt_sender import (
    InfraiEmailClient,
    ReceiptRequest,
    TechnicianFollowUp,
    WorkOrderPhoto,
    send_work_order_receipt,
)


receipt = ReceiptRequest(
    work_order_id="WO-1042",
    customer_email="customer@example.com",
    customer_name="Riley Chen",
    dispatch_status="completed",
    amount=Decimal("189.50"),
    currency="USD",
    technician_name="Morgan Lee",
    photos=(
        WorkOrderPhoto(
            caption="Installed control board",
            url="https://example.com/work-orders/WO-1042/control-board.jpg",
        ),
    ),
    follow_up=TechnicianFollowUp(
        needed=True, note="Morgan will call tomorrow to confirm the temperature reading."
    ),
)

result = send_work_order_receipt(receipt, InfraiEmailClient.from_environment())
print(f"sent receipt: {result.message_id}")
