"""`.env.example` section 2 documents every setting the backend reads, with working values."""

from pathlib import Path

from shosai.core.config.loading import load_settings
from shosai.core.config.sections import (
    HomeSettings,
    SettingsSection,
    StorageSettings,
    home_prefix,
)
from shosai.core.kernel.homes import Home

ENV_EXAMPLE = Path(__file__).resolve().parents[4] / ".env.example"
SECTION_TWO = "# 2. "
SECTION_THREE = "# 3. "
# Переменные раздела 2, которые читает не F1, а слайс (S07 knowledge).
READ_BY_SLICES = {"QDRANT_URL", "QDRANT_API_KEY"}


def section_two() -> dict[str, str]:
    lines = ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith(SECTION_TWO))
    end = next(index for index, line in enumerate(lines) if line.startswith(SECTION_THREE))
    assignments = (line.partition("=") for line in lines[start:end] if not line.startswith("#"))
    return {name: value for name, separator, value in assignments if separator}


def settings_variables() -> set[str]:
    variables: set[str] = set()
    for section in SettingsSection.__subclasses__():
        # Разделы дома читаются с префиксом HOME_<RU|EU>_: база и бакет (ADR 0044).
        per_home = section in {HomeSettings, StorageSettings}
        prefixes = [home_prefix(home) for home in Home] if per_home else [""]
        variables |= {
            f"{prefix}{field}".upper() for prefix in prefixes for field in section.model_fields
        }
    return variables


def test_every_setting_is_documented_and_nothing_stale_is() -> None:
    assert set(section_two()) - READ_BY_SLICES == settings_variables()


def test_the_documented_values_start_a_development_process() -> None:
    load_settings(section_two())
