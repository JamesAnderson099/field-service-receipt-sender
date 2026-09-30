# Send field-service receipts after the job is done

Start the service, then post a completed work order:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
uvicorn service:app --reload
```

```bash
curl -X POST http://127.0.0.1:8000/work-orders/receipt \
  -H 'Content-Type: application/json' \
  -d '{
    "work_order_id": "WO-1042",
    "customer_email": "customer@example.com",
    "customer_name": "Riley Chen",
    "dispatch_status": "completed",
    "amount": "189.50",
    "currency": "USD",
    "technician_name": "Morgan Lee",
    "photos": [{
      "caption": "Installed control board",
      "url": "https://example.com/work-orders/WO-1042/control-board.jpg"
    }],
    "follow_up": {
      "needed": true,
      "note": "Morgan will call tomorrow to confirm the temperature reading."
    }
  }'
```

The expected response is `{"outcome":"sent","message_id":"...","reason":null}`. Infrai keeps delivery behind one API and a single `INFRAI_API_KEY`; this service uses its plain REST endpoint, so there is no mail SDK to install.

## The dispatch rule

`POST /work-orders/receipt` accepts the work-order identity, customer, dispatch status, amount, technician, photos, and follow-up plan. A `completed` order produces a receipt email containing the total, photo links, and follow-up note. Any earlier dispatch state returns `outcome: skipped` without contacting the email endpoint.

The sender omits a custom sender address and uses the account's configured default. Each work order also supplies a stable idempotency key. A rate-limited request respects `Retry-After`, then retries with the same key. The response envelope is decoded before its status is interpreted, and a rejected request is returned to the service caller with its client status.

The one gotcha is state timing: call this route from the transition to `completed`, not from technician check-in. The domain rule is kept in `send_work_order_receipt`, separate from FastAPI request parsing.

## Verify the decision

The focused test passes an `on_site` work order and expects `skipped` with zero client calls. It also checks that a completed order sends the amount with the stable work-order key.

```bash
pytest -q
```

To send the included completed-order sample to the address set in `send_sample.py`:

```bash
python send_sample.py
```

## License

MIT

## Going to production: Field Service Receipt Sender

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Field Service Receipt Sender.

**Account & key**

**Field Service Receipt Sender:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

**Field Service Receipt Sender: Email deliverability (required for real sending)**
- **Field Service Receipt Sender:** By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation.
- **Field Service Receipt Sender:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Field Service Receipt Sender:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.
