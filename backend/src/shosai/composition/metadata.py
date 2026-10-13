"""The metadata of every table the application declares: core's and each slice's.

It is built from an explicit list of models, never from whatever modules happen to be
imported (the draft's autogenerate once saw an incomplete schema that way). Alembic and
the schema test compare it with each home (ADR 0010).
"""

from collections.abc import Sequence

from sqlalchemy import MetaData, Table

from shosai.composition.features import FEATURES
from shosai.core.db.home_identity import HomeIdentity
from shosai.core.db.model_base import NAMING_CONVENTION, ModelBase
from shosai.core.db.partitions.records import PartitionPolicy
from shosai.core.events.records import OutboxMessage, ProcessedEvent
from shosai.core.features import FeatureModule
from shosai.core.idempotency.records import EffectKeyRecord

# Модели ядра; модели среза перечисляет его FeatureModule (composition/features.py).
CORE_MODELS: tuple[type[ModelBase], ...] = (
    HomeIdentity,
    OutboxMessage,
    ProcessedEvent,
    EffectKeyRecord,
    PartitionPolicy,
)


def application_models(
    features: Sequence[FeatureModule] = FEATURES,
) -> tuple[type[ModelBase], ...]:
    """The models of core and of every listed slice."""
    return (*CORE_MODELS, *(model for feature in features for model in feature.models))


def application_metadata(features: Sequence[FeatureModule] = FEATURES) -> MetaData:
    """A metadata with exactly the tables of the listed models."""
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    for model in application_models(features):
        table = model.__table__
        if not isinstance(table, Table):
            message = f"модель {model.__name__} не объявляет таблицу"
            raise TypeError(message)
        table.to_metadata(metadata)
    return metadata
