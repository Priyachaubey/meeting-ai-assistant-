"""Static per-token pricing, sourced from provider docs — not invented.

Sources (checked 2026-06-26, prices change — re-verify periodically against the
provider's own pricing page rather than trusting this file indefinitely):
  - OpenAI gpt-4o-mini:            https://openai.com/api/pricing/  ($0.15 / $0.60 per 1M)
  - OpenAI text-embedding-3-small: https://openai.com/api/pricing/  ($0.02 per 1M, input only)
  - Anthropic claude-sonnet-4-6:   https://platform.claude.com/docs/en/about-claude/pricing
                                    ($3.00 / $15.00 per 1M)

All figures are USD per 1,000,000 tokens, standard (non-batch, non-cached) rates.
"""

PRICING_PER_MILLION_TOKENS_USD: dict[tuple[str, str], dict[str, float]] = {
    ("openai", "gpt-4o-mini"): {"input": 0.15, "output": 0.60},
    ("openai", "text-embedding-3-small"): {"input": 0.02, "output": 0.0},
    ("claude", "claude-sonnet-4-6"): {"input": 3.00, "output": 15.00},
}


def estimate_cost_usd(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> float | None:
    """Returns None (not 0.0) for an unknown provider/model pair — a missing price should
    show up as "unknown" in analytics, not silently as a free call. Caller decides how to
    display None (e.g. "—" rather than "$0.00", which would understate real spend)."""
    rates = PRICING_PER_MILLION_TOKENS_USD.get((provider, model))
    if rates is None:
        return None
    return (prompt_tokens * rates["input"] + completion_tokens * rates["output"]) / 1_000_000
