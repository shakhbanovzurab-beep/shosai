"""The states of an account and what each allows at sign-in (ADR 0045 points 2 and 6)."""

from enum import StrEnum


class AccountState(StrEnum):
    """Where an account is in its life; the directory mirrors it in the EU home."""

    ACTIVE = "active"
    # Оператор закрыл вход; данные на месте.
    FROZEN = "frozen"
    # Вход закрыт навсегда; адрес нельзя зарегистрировать снова.
    BANNED = "banned"
    # Окно в 7 дней: данные скрыты, вход отменяет удаление.
    DELETION_SCHEDULED = "deletion_scheduled"
    # Сага стирает данные срезов.
    DELETING = "deleting"
    # Переезд между домами: записи заморожены.
    TRANSFERRING = "transferring"
    DELETED = "deleted"


class SignInRefusal(StrEnum):
    """Why a correct password still does not open the account; native clients branch on it."""

    BANNED = "account_banned"
    FROZEN = "account_frozen"
    DISABLED = "account_disabled"


def sign_in_refusal(state: AccountState) -> SignInRefusal | None:
    """The refusal a state gives a correct sign-in, or None when the sign-in proceeds.

    A sign-in during the deletion window proceeds and cancels the deletion (ADR 0045).
    """
    match state:
        case AccountState.ACTIVE | AccountState.DELETION_SCHEDULED:
            return None
        case AccountState.FROZEN:
            return SignInRefusal.FROZEN
        case AccountState.BANNED:
            return SignInRefusal.BANNED
        case AccountState.DELETING | AccountState.TRANSFERRING | AccountState.DELETED:
            return SignInRefusal.DISABLED
