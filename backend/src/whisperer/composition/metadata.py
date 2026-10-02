"""The metadata of every table the application declares: core's and each slice's.

It is built from an explicit list of models, never from whatever modules happen to be
imported (the draft's autogenerate once saw an incomplete schema that way). Alembic and
the schema test compare it with each home (ADR 0010).
"""

from sqlalchemy import MetaData, Table

from whisperer.core.db.home_identity import HomeIdentity
from whisperer.core.db.model_base import NAMING_CONVENTION, ModelBase

# Модели ядра; слайсы добавляют свои модели здесь, рядом со своим модулем в композиции.
APPLICATION_MODELS: tuple[type[ModelBase], ...] = (HomeIdentity,)


def application_metadata() -> MetaData:
    """A metadata with exactly the tables of the listed models."""
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    for model in APPLICATION_MODELS:
        table = model.__table__
        if not isinstance(table, Table):
            message = f"модель {model.__name__} не объявляет таблицу"
            raise TypeError(message)
        table.to_metadata(metadata)
    return metadata
