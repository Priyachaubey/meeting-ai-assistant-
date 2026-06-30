"use client";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "@/components/button";
import { api, ApiError, NetworkError } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";

export default function BillingPage() {
  const token = useAuthStore((s) => s.token);
  const [error, setError] = useState<string | null>(null);
  const [redirecting, setRedirecting] = useState(false);

  const { data: subscription, isLoading } = useQuery({
    queryKey: ["subscription", token],
    queryFn: () => api.getSubscription(token as string),
    enabled: !!token,
  });

  async function handleUpgrade() {
    if (!token) return;
    setError(null);
    setRedirecting(true);
    try {
      const { checkout_url } = await api.createCheckoutSession(token);
      window.location.href = checkout_url;
    } catch (err) {
      // Most likely cause locally: STRIPE_SECRET_KEY / STRIPE_PRICE_ID_PRO not set on the API.
      setError(err instanceof ApiError || err instanceof NetworkError ? err.message : "Could not start checkout.");
      setRedirecting(false);
    }
  }

  return (
    <section className="p-6">
      <h1 className="mb-6 text-2xl font-semibold">Billing</h1>
      <div className="rounded-lg border border-ink/10 bg-white p-5">
        {isLoading ? (
          <p className="text-ink/55">Loading plan…</p>
        ) : (
          <>
            <p className="text-xl font-semibold capitalize">{subscription?.plan ?? "free"} plan</p>
            <p className="mt-2 text-ink/60">
              Status: <span className="font-medium">{subscription?.status ?? "inactive"}</span>
              {subscription?.current_period_end && ` · renews ${new Date(subscription.current_period_end).toLocaleDateString()}`}
            </p>
          </>
        )}
        {error && <p className="mt-3 text-sm text-coral">{error}</p>}
        {subscription?.plan !== "pro" && (
          <Button onClick={handleUpgrade} disabled={redirecting} className="mt-5">
            {redirecting ? "Redirecting to Stripe…" : "Upgrade to Pro"}
          </Button>
        )}
      </div>
    </section>
  );
}
