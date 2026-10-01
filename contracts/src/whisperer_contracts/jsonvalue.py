"""Типизированный доступ к разобранному JSON.

`json.load` возвращает `Any`; здесь он один раз сужается до рекурсивного типа
`Json`, а дальше код читает значения только через эти функции. Неверная форма
документа — ошибка входных данных (`ContractInputError`), а не молчаливый пропуск.
"""

import json
from pathlib import Path

type Json = dict[str, Json] | list[Json] | str | int | float | bool | None
type JsonObject = dict[str, Json]


class ContractInputError(ValueError):
    """Входной документ (база или кандидат v2) не соответствует ожидаемой форме."""


def load_json(path: Path) -> Json:
    """Читает JSON-файл; отсутствующий или битый файл — явная ошибка входа."""
    try:
        with path.open(encoding="utf-8") as source:
            loaded: Json = json.load(source)
    except FileNotFoundError as error:
        raise ContractInputError(f"file not found: {path}") from error
    except json.JSONDecodeError as error:
        raise ContractInputError(f"invalid JSON in {path}: {error}") from error
    return loaded


def as_object(value: Json, where: str) -> JsonObject:
    """Значение обязано быть объектом."""
    if not isinstance(value, dict):
        raise ContractInputError(f"{where}: expected an object")
    return value


def as_list(value: Json, where: str) -> list[Json]:
    """Значение обязано быть массивом."""
    if not isinstance(value, list):
        raise ContractInputError(f"{where}: expected an array")
    return value


def as_str(value: Json, where: str) -> str:
    """Значение обязано быть строкой."""
    if not isinstance(value, str):
        raise ContractInputError(f"{where}: expected a string")
    return value


def optional_object(value: Json) -> JsonObject:
    """Объект или пустой объект, если значения нет или это не объект (схемы OpenAPI)."""
    return value if isinstance(value, dict) else {}


def optional_list(value: Json) -> list[Json]:
    """Массив или пустой массив, если значения нет или это не массив."""
    return value if isinstance(value, list) else []


def optional_str(value: Json) -> str:
    """Строка или пустая строка."""
    return value if isinstance(value, str) else ""


def str_list(value: Json, where: str) -> list[str]:
    """Массив строк; отсутствие значения — пустой массив."""
    if value is None:
        return []
    return [as_str(item, f"{where}[{index}]") for index, item in enumerate(as_list(value, where))]
