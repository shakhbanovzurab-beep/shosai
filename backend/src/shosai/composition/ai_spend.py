"""Spend control of a process: ceilings, the kill switch, the operator's views, user guards."""

from contextlib import AsyncExitStack
from datetime import timedelta

import httpx
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from shosai.core.ai.adapters.openrouter import OPENROUTER_API
from shosai.core.ai.calls import PlatformAccount
from shosai.core.ai.limits import MEGABYTE, InputCaps
from shosai.core.ai.port import UserGuards
from shosai.core.ai.resilience.streams import StreamCap
from shosai.core.ai.spend.counters import micro_usd
from shosai.core.ai.spend.guard import Ceilings, SpendGuard, SpendMetrics
from shosai.core.ai.spend.kill_switch import KillSwitch
from shosai.core.ai.spend.operator import SpendOperator
from shosai.core.ai.spend.reports import SpendReports
from shosai.core.ai.spend.standing import OpenRouterCredits, SpendStanding, management_client
from shosai.core.config.loading import Settings
from shosai.core.config.sections import AiGuardSettings, AiSettings, SpendSettings
from shosai.core.db.transactions import HomeTransactions


def kill_switch(settings: SpendSettings, valkey: Redis) -> KillSwitch:
    """The kill switch over Valkey, engaged outright by the setting."""
    return KillSwitch(valkey, forced=settings.ai_kill_switch)


def ceilings_of(settings: SpendSettings) -> Ceilings:
    """The platform's ceilings in micro-USD."""
    platform = {
        PlatformAccount.LANDING_DEMO.value: (
            settings.ai_landing_demo_hourly_usd, settings.ai_landing_demo_daily_usd,
        ),
        PlatformAccount.HELP_ASSISTANT.value: (
            settings.ai_help_assistant_hourly_usd, settings.ai_help_assistant_daily_usd,
        ),
        PlatformAccount.ADMIN_ASSISTANT.value: (
            settings.ai_admin_assistant_hourly_usd, settings.ai_admin_assistant_daily_usd,
        ),
        PlatformAccount.SYSTEM.value: (settings.ai_system_hourly_usd, settings.ai_system_daily_usd),
    }  # fmt: skip
    return Ceilings(
        global_hour=micro_usd(settings.ai_global_hourly_usd),
        global_day=micro_usd(settings.ai_global_daily_usd),
        platform={
            name: (micro_usd(hour), micro_usd(day)) for name, (hour, day) in platform.items()
        },
        lease=timedelta(seconds=settings.ai_reservation_lease_seconds),
    )


def credits_client(ai: AiSettings, stack: AsyncExitStack) -> httpx.AsyncClient | None:
    """OpenRouter's management client for the balance; None without its key."""
    if ai.openrouter_management_key is None:
        return None
    base_url = OPENROUTER_API if ai.openrouter_base_url is None else str(ai.openrouter_base_url)
    client = management_client(ai.openrouter_management_key.get_secret_value(), base_url)
    stack.push_async_callback(client.aclose)
    return client


def spend_control(
    settings: Settings,
    valkey: Redis,
    registry: CollectorRegistry,
    transactions: HomeTransactions,
    stack: AsyncExitStack,
) -> tuple[SpendGuard, SpendOperator]:
    """Spend control and the operator's views over one kill switch."""
    switch = kill_switch(settings.spend, valkey)
    ceilings = ceilings_of(settings.spend)
    business = settings.calendar.business
    guard = SpendGuard(valkey, ceilings, switch, SpendMetrics(registry), business)
    operator = SpendOperator(
        reports=SpendReports(transactions, business),
        standing=SpendStanding(valkey, ceilings, switch, business),
        credits=OpenRouterCredits(credits_client(settings.ai, stack)),
        kill_switch=switch,
    )
    return guard, operator


def user_guards(settings: AiGuardSettings, valkey: Redis) -> UserGuards:
    """The input caps and the interactive-stream cap from settings."""
    caps = InputCaps(
        context_tokens=settings.ai_max_context_tokens,
        images=settings.ai_max_images,
        image_bytes=settings.ai_max_image_mb * MEGABYTE,
    )
    return UserGuards(caps=caps, streams=StreamCap(valkey, settings.ai_interactive_streams))
