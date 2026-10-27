"""A model of the catalogue and the tier its price proposes (studio plan §3.6, ADR 0074).

The operator lists OpenRouter models by id; their name, maker, window, output limit, what
they read and which parameters they take come from OpenRouter's model list. A listed model
is retired, never deleted: costs and people's choices name it softly. The price in force
proposes the tier — frontier above the platform's line, standard otherwise — and a proposal
changes nothing until the admin confirms it; a declined proposal is not raised again while
the price keeps proposing the same tier (ST-D4, amended by the owner).
"""

import hashlib
import re
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Final

from shosai.features.studio.domain.roles import MAX_TOKENS_CAP, Capability, Tier

# Id модели входит в события, а код события — до 64 символов.
SLUG_MAX: Final = 64
SLUG_HASH: Final = 8
MAKER_SEPARATOR: Final = ": "
PER_MILLION: Final = Decimal(1_000_000)
_NOT_SLUG: Final = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class Listing:
    """What OpenRouter's model list says of one model."""

    openrouter_id: str
    name: str
    context_length: int
    max_output_tokens: int | None
    input_modalities: frozenset[str]
    output_modalities: frozenset[str]
    parameters: frozenset[str]


@dataclass(frozen=True, slots=True)
class CatalogueModel:
    """A model people may be offered, with its confirmed tier and a pending proposal."""

    id: str
    openrouter_id: str
    name: str
    maker: str
    context_length: int
    max_output_tokens: int
    capabilities: frozenset[Capability]
    supports_temperature: bool
    supports_reasoning: bool
    tier: Tier
    tier_proposed: Tier | None = None
    tier_declined: Tier | None = None
    enabled: bool = True
    retired: bool = False

    @property
    def usable(self) -> bool:
        """Whether the model may answer anyone: switched on and still listed."""
        return self.enabled and not self.retired

    @property
    def output_limit(self) -> int:
        """The most output tokens a person may ask of it."""
        return min(self.max_output_tokens, MAX_TOKENS_CAP)

    def can(self, needs: frozenset[Capability]) -> bool:
        """Whether the model reads everything a call needs."""
        return needs <= self.capabilities


def slug_of(openrouter_id: str) -> str:
    """The model's URL-safe id: its OpenRouter id in lowercase letters, digits and dashes; a
    long id is cut and ends with a hash of the whole, so two ids never share a slug."""
    slug = _NOT_SLUG.sub("-", openrouter_id.lower()).strip("-")
    if not slug:
        message = f"у модели {openrouter_id!r} нет букв и цифр для её id"
        raise ValueError(message)
    if len(slug) <= SLUG_MAX:
        return slug
    digest = hashlib.sha256(openrouter_id.encode()).hexdigest()[:SLUG_HASH]
    return f"{slug[: SLUG_MAX - SLUG_HASH - 1].rstrip('-')}-{digest}"


def capabilities_of(listing: Listing) -> frozenset[Capability]:
    """What the model reads, from its modalities: text out, and pictures in besides text."""
    if "text" not in listing.output_modalities:
        return frozenset()
    if "image" in listing.input_modalities:
        return frozenset({Capability.TEXT, Capability.VISION})
    return frozenset({Capability.TEXT})


def maker_and_name(listing: Listing) -> tuple[str, str]:
    """The maker and the model's own name, from OpenRouter's "Maker: Name" or its id."""
    maker, separator, name = listing.name.partition(MAKER_SEPARATOR)
    if separator and maker.strip() and name.strip():
        return maker.strip(), name.strip()
    return listing.openrouter_id.partition("/")[0], listing.name.strip() or listing.openrouter_id


def described(model: CatalogueModel, listing: Listing) -> CatalogueModel:
    """The model with what the list says of it now; its id, tier and switches stay."""
    maker, name = maker_and_name(listing)
    output = listing.max_output_tokens or listing.context_length
    return replace(
        model,
        name=name,
        maker=maker,
        context_length=listing.context_length,
        max_output_tokens=min(output, listing.context_length),
        capabilities=capabilities_of(listing),
        supports_temperature="temperature" in listing.parameters,
        supports_reasoning="reasoning" in listing.parameters,
    )


def listed(listing: Listing, tier: Tier) -> CatalogueModel:
    """A new entry of the catalogue, switched off until the admin switches it on."""
    blank = CatalogueModel(
        id=slug_of(listing.openrouter_id),
        openrouter_id=listing.openrouter_id,
        name="",
        maker="",
        context_length=0,
        max_output_tokens=0,
        capabilities=frozenset(),
        supports_temperature=False,
        supports_reasoning=False,
        tier=tier,
        enabled=False,
    )
    return described(blank, listing)


def priced_tier(output_usd_per_token: Decimal | None, line_usd_per_million: Decimal) -> Tier | None:
    """The tier an output price proposes; none without a price."""
    if output_usd_per_token is None:
        return None
    if output_usd_per_token * PER_MILLION > line_usd_per_million:
        return Tier.FRONTIER
    return Tier.STANDARD


def proposed(model: CatalogueModel, priced: Tier | None) -> CatalogueModel:
    """The model after a price was read: a new proposal, the old one kept, or none needed."""
    if priced is None:
        return model
    if priced is model.tier:
        return replace(model, tier_proposed=None, tier_declined=None)
    if priced in {model.tier_proposed, model.tier_declined}:
        return model
    return replace(model, tier_proposed=priced)


def confirmed(model: CatalogueModel) -> CatalogueModel:
    """The model in its proposed tier, from now on; callers check there is a proposal."""
    tier = model.tier_proposed if model.tier_proposed is not None else model.tier
    return replace(model, tier=tier, tier_proposed=None, tier_declined=None)


def declined(model: CatalogueModel) -> CatalogueModel:
    """The model in its tier, the proposal set aside until the price proposes otherwise."""
    return replace(model, tier_proposed=None, tier_declined=model.tier_proposed)
