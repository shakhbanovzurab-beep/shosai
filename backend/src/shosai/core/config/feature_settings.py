"""Settings sections a slice declares for itself (identity plan §3.2).

A slice lists its sections on its `FeatureModule`; `load_settings` reads them from the
same mapping as core's, collects their problems with core's, and keeps them here. The
slice reads its own section from `CoreServices.settings.features` when it is built, and
its production checks read it from the same place.
"""

from collections.abc import Iterable, Mapping
from types import MappingProxyType

from shosai.core.config.sections import SettingsSection


class FeatureSettings:
    """The slices' settings sections, by section class."""

    def __init__(self, sections: Iterable[SettingsSection] = ()) -> None:
        found: dict[type[SettingsSection], SettingsSection] = {}
        for section in sections:
            if type(section) in found:
                message = f"раздел настроек {type(section).__name__} прочитан дважды"
                raise ValueError(message)
            found[type(section)] = section
        self._sections: Mapping[type[SettingsSection], SettingsSection] = MappingProxyType(found)

    def get[S: SettingsSection](self, section: type[S]) -> S:
        """The section of the class; a section no slice declared is a composition error."""
        value = self._sections.get(section)
        if not isinstance(value, section):
            message = f"раздел настроек {section.__name__} не объявлен ни одним срезом"
            raise LookupError(message)
        return value
