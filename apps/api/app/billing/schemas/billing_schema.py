from pydantic import BaseModel


class CheckoutRequest(BaseModel):
    price_id: str | None = None  # falls back to settings.stripe_price_id_pro if omitted


class CheckoutResponse(BaseModel):
    checkout_url: str


class SubscriptionOut(BaseModel):
    plan: str
    status: str
    current_period_end: str | None = None
