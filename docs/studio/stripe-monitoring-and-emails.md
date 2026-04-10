# Stripe: webhook monitoring and trial emails

## 1. Monitoring webhook failures (Stripe Dashboard)

1. Open [Stripe Dashboard → Developers → Webhooks](https://dashboard.stripe.com/webhooks).
2. Select your destination (**Immersive Labs studio-worker billing**).
3. Use **Event deliveries** (or **Logs**) to filter **failed** attempts. Stripe retries automatically; repeated failures usually mean a bad URL, TLS/proxy issues, or your worker returning **4xx/5xx**.
4. If your account shows **email notifications** for webhook failures (wording varies), enable them so you get alerted without opening the Dashboard daily.

**Log shipping:** Your worker logs structured lines on problems, for example:

- `stripe_webhook_reject` — missing header, bad payload, or signature mismatch.
- `stripe_webhook_handler_failed` — exception inside `handle_stripe_event` (Stripe will retry).

Search your host logs for those strings or ship logs to your usual aggregator (Datadog, CloudWatch, etc.) and alert on them.

## 2. External uptime check (API health)

`GET /api/studio/health` returns JSON including:

- `status`: `"ok"` when the process is up.
- `stripe_webhook_configured`: `true` when `STRIPE_WEBHOOK_SECRET` is set on that instance (helps catch misconfigured deploys).

This does **not** prove Stripe can deliver webhooks (firewall, path, signing still matter), but it complements Dashboard delivery logs.

**GitHub Actions:** The repo includes [`.github/workflows/studio-api-uptime.yml`](../../.github/workflows/studio-api-uptime.yml). Add a repository **secret** `STUDIO_PUBLIC_HEALTH_URL` with the **public API origin** (no trailing slash), e.g. `https://api.immersivelabs.space`. You can also paste the full health URL (`https://api.immersivelabs.space/api/studio/health`); the workflow strips `/api/studio/health` before appending it so you do not get a doubled path and a FastAPI **`{"detail":"Not Found"}`** from `/api/studio/health/api/studio/health`. **`GET https://api…/`** (root only) is not the health route — use **`/api/studio/health`**. Do **not** use a bare apex like `https://immersivelabs.space` unless that hostname actually serves the health path. Avoid a trailing newline when pasting the secret. The workflow runs on a schedule and fails if health is not HTTP 200 or `status` is not `ok`.

## 3. Trial ending — Stripe’s customer emails (recommended)

Stripe can email subscribers before a trial ends (no app code required):

1. Dashboard → **Settings** → **Billing** → **Customer emails** (or **Subscriptions and emails**, depending on UI version).
2. Enable the option for **trial will end** / **upcoming renewal** reminders as offered for your account.
3. Ensure your **Branding** and **Public business information** include a recognizable sender and support contact.

These emails are independent of the `customer.subscription.trial_will_end` webhook.

## 4. Trial ending — optional automation from the worker

When Stripe sends `customer.subscription.trial_will_end`, the worker:

- Logs an **info** line: `stripe_subscription_trial_will_end …`
- If **`STUDIO_TRIAL_END_NOTIFY_WEBHOOK_URL`** is set, **POST**s JSON to that URL:

```json
{
  "event": "customer.subscription.trial_will_end",
  "tenant_id": "<uuid or null>",
  "stripe_customer_id": "cus_...",
  "stripe_subscription_id": "sub_...",
  "trial_end": 1234567890
}
```

Use this with **Zapier**, **Make**, **Slack incoming webhooks**, or your own endpoint to send email/SMS/Slack. Failures to notify are logged as warnings and do **not** fail the webhook (Stripe still gets `200`).

See `apps/studio-worker/.env.example` for the variable name.
