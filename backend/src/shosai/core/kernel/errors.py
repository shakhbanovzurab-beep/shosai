"""Errors a slice raises for its caller; the web layer renders them (ADR 0008).

The error is framework-free: a stable machine code that a client turns into text through
i18n, an HTTP status from the standard library, optional parameters for the client's
message and, on a route whose draft contract has another shape, the compatible `detail`.
Domain code never builds a response body and never sends a user-facing sentence.
"""

import math
import re
from collections.abc import Mapping
from http import HTTPStatus
from types import MappingProxyType

# Код — ключ i18n `errors:<code>` у клиента, поэтому только snake_case: точка в i18next
# разделяет уровни ключа.
ERROR_CODE = re.compile(r"[a-z][a-z0-9_]{0,63}")
# Текстовый параметр — код или идентификатор: «@», пробел и не-латиница не проходят,
# так что адрес почты, имя или фраза в ответ через параметр не попадут.
PARAM_TEXT = re.compile(r"[A-Za-z0-9_.:-]{1,64}")
FIRST_ERROR_STATUS = 400
LAST_ERROR_STATUS = 599

type ErrorParam = int | float | bool | str
type DetailValue = str | int | float | bool
type CompatibleDetail = str | Mapping[str, DetailValue]


class AppError(Exception):
    """An expected failure the caller is told about: a code, a status and optional params.

    `detail` is set only on a route whose draft contract gives the top-level `detail`
    another shape (ADR 0008); by default the response repeats the code there.
    """

    def __init__(
        self,
        code: str,
        status: HTTPStatus,
        *,
        params: Mapping[str, ErrorParam] | None = None,
        detail: CompatibleDetail | None = None,
    ) -> None:
        if not ERROR_CODE.fullmatch(code):
            message = "код ошибки — snake_case до 64 символов"
            raise ValueError(message)
        if not FIRST_ERROR_STATUS <= status <= LAST_ERROR_STATUS:
            message = "статус ошибки — 4xx или 5xx"
            raise ValueError(message)
        checked = dict(params or {})
        for name, value in checked.items():
            check_param(name, value)
        super().__init__(code)
        self.code = code
        self.status = status
        self.params: Mapping[str, ErrorParam] = MappingProxyType(checked)
        self.detail = detail


def check_param(name: str, value: ErrorParam) -> None:
    """Reject a parameter that could carry personal data or break the JSON body."""
    if not ERROR_CODE.fullmatch(name):
        message = "имя параметра ошибки — snake_case до 64 символов"
        raise ValueError(message)
    if isinstance(value, str) and not PARAM_TEXT.fullmatch(value):
        message = f"параметр {name}: текст — только код или идентификатор"
        raise ValueError(message)
    if isinstance(value, float) and not math.isfinite(value):
        message = f"параметр {name}: число должно быть конечным"
        raise ValueError(message)
