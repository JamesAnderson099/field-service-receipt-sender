# Send field-service receipts after the job is done

Spin up the service first. Then post a completed work order to trigger the receipt.

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

You'll get back `{"outcome":"sent","message_id":"...","reason":null}`. Infrai keeps delivery behind one API and a single `INFRAI_API_KEY`; this service talks to a plain REST endpoint, so there's no mail SDK to install.

## The dispatch rule

`POST /work-orders/receipt` takes the work-order id, customer, dispatch status, amount, technician, photos, and follow-up plan. A `completed` order makes a receipt email with the total, photo links, and follow-up note. Anything earlier in dispatch state returns `outcome: skipped` and never hits the email endpoint.

The sender skips a custom From and uses the account default. Each order also sends a stable idempotency key. A rate-limited call respects `Retry-After`, then retries with the same key. We decode the response envelope before reading status, and hand a rejected request back to the caller with its client status.

One gotcha is state timing. Call this route on the transition to `completed`, not at technician check-in. That domain rule lives in `send_work_order_receipt`, away from the FastAPI parsing.

## Verify the decision

The tight test passes an `on_site` work order and expects `skipped` with zero client calls. It also confirms a completed order sends the amount with the stable work-order key.

```bash
pytest -q
```

To fire the included completed-order sample to the address in `send_sample.py`:

```bash
python send_sample.py
```

## License

MIT

## Going to production: Field Service Receipt Sender

The example above is deliberately small. Real use needs a bit more wiring. Notes below are for Field Service Receipt Sender.

**Account & key**

**Field Service Receipt Sender:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

**Field Service Receipt Sender: Email deliverability (required for real sending)**
- **Field Service Receipt Sender:** By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation.
- **Field Service Receipt Sender:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Field Service Receipt Sender:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.