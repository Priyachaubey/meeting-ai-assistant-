from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.billing.schemas.billing_schema import CheckoutRequest, CheckoutResponse, SubscriptionOut
from app.billing.services.stripe_service import BillingError, construct_webhook_event, create_checkout_session
from app.core.security import get_current_user_id
from app.database.session import get_db
from app.models.entities import Subscription, User

router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    payload: CheckoutRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> CheckoutResponse:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    try:
        checkout_url = create_checkout_session(user.email, payload.price_id)
    except BillingError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return CheckoutResponse(checkout_url=checkout_url)


@router.get("/subscription", response_model=SubscriptionOut)
async def get_subscription(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> SubscriptionOut:
    sub = db.query(Subscription).filter(Subscription.owner_id == user_id).first()
    if not sub:
        return SubscriptionOut(plan="free", status="inactive")
    return SubscriptionOut(
        plan=sub.plan,
        status=sub.status,
        current_period_end=sub.current_period_end.isoformat() if sub.current_period_end else None,
    )


@router.post("/webhook", status_code=status.HTTP_204_NO_CONTENT)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> None:
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = construct_webhook_event(payload, signature)
    except BillingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    data = event["data"]["object"]

    if event["type"] == "checkout.session.completed":
        user = db.query(User).filter(User.email == data.get("customer_email")).first()
        if user:
            _upsert_subscription(
                db,
                owner_id=user.id,
                stripe_customer_id=data.get("customer"),
                stripe_subscription_id=data.get("subscription"),
                plan="pro",
                status="active",
            )

    elif event["type"] in ("customer.subscription.updated", "customer.subscription.deleted"):
        sub = db.query(Subscription).filter(Subscription.stripe_subscription_id == data.get("id")).first()
        if sub:
            sub.status = "active" if event["type"] == "customer.subscription.updated" else "canceled"
            period_end = data.get("current_period_end")
            if period_end:
                sub.current_period_end = datetime.utcfromtimestamp(period_end)
            db.commit()

    return None


def _upsert_subscription(
    db: Session,
    *,
    owner_id: str,
    stripe_customer_id: str | None,
    stripe_subscription_id: str | None,
    plan: str,
    status: str,
) -> None:
    sub = db.query(Subscription).filter(Subscription.owner_id == owner_id).first()
    if not sub:
        sub = Subscription(owner_id=owner_id)
        db.add(sub)
    sub.stripe_customer_id = stripe_customer_id
    sub.stripe_subscription_id = stripe_subscription_id
    sub.plan = plan
    sub.status = status
    db.commit()
