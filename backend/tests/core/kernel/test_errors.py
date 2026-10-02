"""A domain error accepts only a code, an error status and params free of personal data."""

from http import HTTPStatus

import pytest
from hypothesis import given
from hypothesis import strategies as st

from whisperer.core.kernel.errors import PARAM_TEXT, AppError


def test_an_error_keeps_its_code_status_params_and_detail() -> None:
    error = AppError(
        "seat_limit_reached",
        HTTPStatus.PAYMENT_REQUIRED,
        params={"seats": 30, "ratio": 0.5, "trial": False, "org_id": "0199a3c2-e7f8"},
        detail={"code": "seats"},
    )

    assert str(error) == "seat_limit_reached"
    assert error.status is HTTPStatus.PAYMENT_REQUIRED
    assert dict(error.params) == {
        "seats": 30,
        "ratio": 0.5,
        "trial": False,
        "org_id": "0199a3c2-e7f8",
    }
    assert error.detail == {"code": "seats"}


def test_params_cannot_be_changed_after_the_error_is_raised() -> None:
    error = AppError("item_locked", HTTPStatus.CONFLICT, params={"item_id": 7})

    with pytest.raises(TypeError):
        error.params["item_id"] = 8  # type: ignore[index]


@pytest.mark.parametrize("code", ["Item_locked", "item-locked", "item.locked", "", "x" * 65])
def test_a_code_that_is_not_snake_case_is_rejected(code: str) -> None:
    with pytest.raises(ValueError, match="snake_case"):
        AppError(code, HTTPStatus.CONFLICT)


@pytest.mark.parametrize("status", [HTTPStatus.OK, HTTPStatus.FOUND])
def test_a_status_that_is_not_an_error_is_rejected(status: HTTPStatus) -> None:
    with pytest.raises(ValueError, match="4xx"):
        AppError("item_locked", status)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("email", "someone@example.com"),
        ("name", "Иван"),
        ("phrase", "two words"),
        ("Bad-Name", 1),
        ("ratio", float("inf")),
        ("ratio", float("nan")),
    ],
)
def test_a_param_that_could_carry_personal_data_or_break_json_is_rejected(
    name: str, value: str | float
) -> None:
    with pytest.raises(ValueError, match="параметр"):
        AppError("item_locked", HTTPStatus.CONFLICT, params={name: value})


@given(st.text(max_size=80))
def test_a_text_param_is_accepted_exactly_when_it_is_a_code_or_an_id(text: str) -> None:
    accepted = True
    try:
        AppError("item_locked", HTTPStatus.CONFLICT, params={"value": text})
    except ValueError:
        accepted = False

    assert accepted == bool(PARAM_TEXT.fullmatch(text))
    if accepted:
        assert "@" not in text
        assert not any(character.isspace() for character in text)
