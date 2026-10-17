"""Workspaces' invariant monitors (§16.4): access never wider than RLS, seats never overrun.

Each monitor pages; its gauge is set by a periodic check (`application/invariant_checks`).
"""

from shosai.core.observability.objectives import InvariantMonitor, StaysAtMost

WORKSPACES_MONITORS = (
    InvariantMonitor(
        name="policy_disagrees_with_rls",
        invariant="inv-14",
        summary="Политика доступа открывает чужие строки пространств",
        explanation=(
            "Самопроверка нашла строки пространств, которые политика доступа показала бы "
            "человеку вне его пространств. Сейчас их скрывает вторая линия защиты в базе, "
            "но правило доступа сломано, и данные одной компании могут попасть к другой."
        ),
        condition=StaysAtMost("shosai_workspaces_policy_rls_disagreements"),
    ),
    InvariantMonitor(
        name="workspace_over_seats",
        invariant="inv-16",
        summary="В пространстве людей больше, чем оплачено мест",
        explanation=(
            "Участников и приглашений больше оплаченных мест: компания пользуется тем, "
            "за что не платит, или оплата уменьшилась без пересчёта мест."
        ),
        condition=StaysAtMost("shosai_workspaces_over_seats"),
    ),
)
