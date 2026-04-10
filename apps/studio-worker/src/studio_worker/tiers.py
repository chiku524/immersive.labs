from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tier:
    """Subscription tier for indie / small-team SaaS (enforced server-side)."""

    id: str
    display_name: str
    monthly_credits: int
    max_concurrent_jobs: int
    textures_allowed: bool


TIERS: dict[str, Tier] = {
    "free": Tier(
        id="free",
        display_name="Free",
        monthly_credits=40,
        max_concurrent_jobs=1,
        textures_allowed=False,
    ),
    "indie": Tier(
        id="indie",
        display_name="Indie",
        monthly_credits=600,
        max_concurrent_jobs=2,
        textures_allowed=True,
    ),
    "team": Tier(
        id="team",
        display_name="Small team",
        monthly_credits=3000,
        max_concurrent_jobs=5,
        textures_allowed=True,
    ),
    # Synthetic tier when STUDIO_API_AUTH_REQUIRED is off (local development)
    "dev": Tier(
        id="dev",
        display_name="Development",
        monthly_credits=10_000_000,
        max_concurrent_jobs=50,
        textures_allowed=True,
    ),
}


def get_tier(tier_id: str) -> Tier:
    t = TIERS.get(tier_id)
    if t is None:
        return TIERS["free"]
    return t


# Credit costs (tunable product knobs)
CREDIT_COST_GENERATE_SPEC = 1
CREDIT_COST_RUN_JOB = 2
CREDIT_COST_RUN_JOB_TEXTURES = 6
