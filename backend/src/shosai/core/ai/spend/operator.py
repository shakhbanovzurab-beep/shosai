"""What the operator's screens get from spend control (F6-D5): reports, standing, balance,
the kill switch. `studio` and `identity` call these from their own admin routers."""

from dataclasses import dataclass

from shosai.core.ai.spend.kill_switch import KillSwitch
from shosai.core.ai.spend.reports import SpendReports
from shosai.core.ai.spend.standing import OpenRouterCredits, SpendStanding


@dataclass(frozen=True, slots=True)
class SpendOperator:
    """The operator's view and controls of AI spend."""

    reports: SpendReports
    standing: SpendStanding
    credits: OpenRouterCredits
    kill_switch: KillSwitch
