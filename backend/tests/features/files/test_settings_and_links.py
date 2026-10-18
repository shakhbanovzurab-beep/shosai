"""Files' settings and gate, download links on the edge's address, copies' names (step 4)."""

import pytest

from shosai.core.config.gate import UnsafeConfigurationError, enforce_production_gate
from shosai.core.config.loading import load_settings
from shosai.core.kernel.homes import Home
from shosai.features.files.domain.names import NAME_MAX, copy_name
from shosai.features.files.infrastructure.download_links import edge_link
from shosai.features.files.settings import FilesSettings, downloads_through_edge
from tests.core.config.sample_environ import local_environ, production_environ

SIGNED = "https://s3.example/bucket/u/1/f/2?X-Amz-Signature=abc&response-content-type=text%2Fplain"


def test_production_needs_the_edge_and_development_may_go_straight_to_the_bucket() -> None:
    environ = production_environ()
    del environ["FILES_DOWNLOAD_BASE_URL"]

    with pytest.raises(UnsafeConfigurationError) as raised:
        enforce_production_gate(load_settings(environ, [FilesSettings]), [downloads_through_edge])
    enforce_production_gate(
        load_settings(production_environ(), [FilesSettings]), [downloads_through_edge]
    )
    local = load_settings(local_environ(), [FilesSettings]).features.get(FilesSettings)

    assert [v.setting for v in raised.value.violations] == ["FILES_DOWNLOAD_BASE_URL"]
    assert local.files_download_base_url is None


def test_a_link_keeps_the_bucket_path_and_signature_under_the_home() -> None:
    assert edge_link(SIGNED, Home.RU, "https://shosai.tech/dl/") == (
        "https://shosai.tech/dl/ru/bucket/u/1/f/2"
        "?X-Amz-Signature=abc&response-content-type=text%2Fplain"
    )
    assert edge_link(SIGNED, Home.EU, None) == SIGNED


def test_a_copy_takes_the_first_free_number_within_the_name_limit() -> None:
    assert copy_name("Report.pdf", set()) == "Report (2).pdf"
    assert copy_name("Report.pdf", {"Report (2).pdf"}) == "Report (3).pdf"
    assert copy_name(".env", set()) == ".env (2)"
    assert len(copy_name("a" * NAME_MAX + ".pdf", set())) == NAME_MAX
    assert copy_name("a" * NAME_MAX + ".pdf", set()).endswith(" (2).pdf")
    assert len(copy_name("a." + "x" * (NAME_MAX - 2), set())) == NAME_MAX
