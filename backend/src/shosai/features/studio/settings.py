"""Studio's settings (`STUDIO_*`), documented in `.env.example` section 2."""

from decimal import Decimal

from pydantic import Field

from shosai.core.config.sections import SettingsSection


class StudioSettings(SettingsSection):
    """The line between standard and frontier models (ST-D4, ADR 0074)."""

    # Цена выхода в долларах за миллион токенов, выше которой цена предлагает уровень frontier;
    # уровень меняет только админ, подтверждая предложение.
    studio_frontier_output_usd_per_m: Decimal = Field(default=Decimal(6), gt=0)
