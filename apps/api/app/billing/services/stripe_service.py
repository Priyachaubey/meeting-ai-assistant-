import stripe

from app.core.config import settings

# Written against stripe-python's classic global-client API (stripe.api_key + stripe.checkout.
# Session.create + stripe.error.*), which the SDK has kept for backward compatibility across
# major versions. Not exercised against a live Stripe account (no network access in this
# sandbox) — run `stripe.checkout.Session.create(...)` once locally against your pinned
# `stripe` version before relying on this in production; if it's moved to the newer
# `stripe.StripeClient(...)` object style, these calls will need updating to match.


class BillingError(Exception):
    """Configuration or Stripe API failure — never silently fall back to a fake checkout URL."""


def _client() -> None:
    if not settings.stripe_secret_key:
        raise BillingError("STRIPE_SECRET_KEY is not set — configure it in .env before using billing.")
    stripe.api_key = settings.stripe_secret_key


def create_checkout_session(customer_email: str, price_id: str | None) -> str:
    """Creates a real Stripe Checkout Session and returns its hosted URL.
    NOTE: like the other provider integrations in this pass, this is written against Stripe's
    documented Checkout API from training knowledge and hasn't been exercised against a live
    Stripe account (no network access in this sandbox) — test with a real test-mode secret key
    before going live."""
    _client()
    resolved_price_id = price_id or settings.stripe_price_id_pro
    if not resolved_price_id:
        raise BillingError("No price_id given and STRIPE_PRICE_ID_PRO is not set.")
    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer_email=customer_email,
            line_items=[{"price": resolved_price_id, "quantity": 1}],
            success_url=f"{settings.web_url}/billing?checkout=success",
            cancel_url=f"{settings.web_url}/billing?checkout=cancelled",
        )
    except stripe.error.StripeError as exc:
        raise BillingError(f"Stripe checkout session creation failed: {exc}") from exc
    if not session.url:
        raise BillingError("Stripe did not return a checkout URL.")
    return session.url


def construct_webhook_event(payload: bytes, signature_header: str) -> stripe.Event:
    if not settings.stripe_webhook_secret:
        raise BillingError("STRIPE_WEBHOOK_SECRET is not set — webhook signatures cannot be verified.")
    try:
        return stripe.Webhook.construct_event(payload, signature_header, settings.stripe_webhook_secret)
    except (stripe.error.SignatureVerificationError, ValueError) as exc:
        raise BillingError(f"Invalid Stripe webhook signature: {exc}") from exc
