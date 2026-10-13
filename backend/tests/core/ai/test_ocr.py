"""Mistral OCR through the port: the document inline, pages in order, a row per billed page."""

import base64
import json
from decimal import Decimal

import httpx
import pytest

from shosai.core.ai.adapters.mistral_ocr import MISTRAL_API
from shosai.core.ai.calls import ModelRef, ModelRoute, Provider
from shosai.core.ai.documents import OcrRequest
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.kernel.homes import Home
from tests.core.ai.bench import AiBench, ai_bench, context, set_prices
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

OCR = ModelRef(Provider.MISTRAL, "mistral-ocr-4-1")
SCAN = OcrRequest(b"%PDF-1.7 probe", "application/pdf", pages=(0, 1))
A4: dict[str, int] = {"dpi": 200, "width": 1654, "height": 2339}
FIRST: dict[str, object] = {"index": 0, "markdown": "# Contract", "dimensions": A4}
SECOND: dict[str, object] = {"index": 1, "markdown": "## Terms", "dimensions": A4}
PAGES: dict[str, object] = {
    "model": "mistral-ocr-4-1",
    "pages": [SECOND, FIRST],
    "usage_info": {"pages_processed": 2, "doc_size_bytes": None},
}


class Mistral:
    """Mistral's OCR endpoint as a transport double: one scripted answer, the bodies sent."""

    def __init__(self, answer: httpx.Response) -> None:
        self.answer = answer
        self.bodies: list[dict[str, object]] = []

    def client(self) -> httpx.AsyncClient:
        """A client whose transport is this double."""
        return httpx.AsyncClient(
            base_url=MISTRAL_API + "/", transport=httpx.MockTransport(self.handle)
        )

    def handle(self, request: httpx.Request) -> httpx.Response:
        """Record the body and answer."""
        assert request.url.path == "/v1/ocr"
        self.bodies.append(json.loads(request.content))
        return self.answer


async def reading(homes: DatabaseAccess, mistral: Mistral) -> AiBench:
    """A bench with OCR priced per page."""
    await set_prices(homes.transactions, OCR, page="0.004")
    return ai_bench(homes.transactions, mistral_ocr=mistral.client())


async def test_a_scan_is_read_page_by_page_and_billed_per_page(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    mistral = Mistral(httpx.Response(200, json=PAGES))
    bench = await reading(homes, mistral)

    result = await bench.providers.ocr(context("upload:9:ocr"), ModelRoute(OCR), SCAN)

    [body] = mistral.bodies
    [row] = await fetch_rows(
        run_slot.claimed.connections[Home.EU],
        "SELECT kind, units, unit, cost_usd, cost_source FROM provider_costs",
    )
    encoded = base64.b64encode(SCAN.data).decode("ascii")
    assert body["document"] == {
        "type": "document_url", "document_url": f"data:application/pdf;base64,{encoded}",
    }  # fmt: skip
    assert (body["model"], body["pages"]) == ("mistral-ocr-4-1", [0, 1])
    assert [(page.index, page.markdown) for page in result.pages] == [
        (0, "# Contract"), (1, "## Terms"),
    ]  # fmt: skip
    assert (row["kind"], row["units"], row["unit"]) == ("ocr", Decimal("2.000"), "page")
    assert (row["cost_usd"], row["cost_source"]) == (Decimal("0.0080000000"), "priced")


async def test_an_image_goes_as_an_image_url(homes: DatabaseAccess) -> None:
    mistral = Mistral(httpx.Response(200, json={**PAGES, "pages": [FIRST]}))
    bench = await reading(homes, mistral)

    await bench.providers.ocr(context(), ModelRoute(OCR), OcrRequest(b"\x89PNG probe", "image/png"))

    [body] = mistral.bodies
    document = body["document"]
    assert isinstance(document, dict)
    assert document["type"] == "image_url"
    assert str(document["image_url"]).startswith("data:image/png;base64,")
    assert "pages" not in body


@pytest.mark.parametrize(
    ("answer", "failure"),
    [
        (httpx.Response(200, json={"pages": [], "usage_info": {}}), AiFailure.PROVIDER_ERROR),
        (httpx.Response(422, json={"detail": "bad document"}), AiFailure.PROVIDER_ERROR),
        (httpx.Response(429, json={"message": "slow down"}), AiFailure.RATE_LIMITED),
    ],
)
async def test_a_failed_read_says_why_and_writes_no_row(
    homes: DatabaseAccess, run_slot: RunSlot, answer: httpx.Response, failure: AiFailure
) -> None:
    bench = await reading(homes, Mistral(answer))

    with pytest.raises(AiCallError) as failed:
        await bench.providers.ocr(context(), ModelRoute(OCR), SCAN)

    assert failed.value.failure is failure
    assert (
        await fetch_rows(run_slot.claimed.connections[Home.EU], "SELECT id FROM provider_costs")
        == []
    )


async def test_without_its_key_ocr_is_refused(homes: DatabaseAccess) -> None:
    await set_prices(homes.transactions, OCR, page="0.004")
    bench = ai_bench(homes.transactions)

    with pytest.raises(AiCallError) as refused:
        await bench.providers.ocr(context(), ModelRoute(OCR), SCAN)

    assert refused.value.failure is AiFailure.MODEL_UNAVAILABLE


@pytest.mark.parametrize(
    ("data", "media_type", "pages"),
    [(b"", "application/pdf", ()), (b"x", "text/plain", ()), (b"x", "image/png", (-1,))],
)
def test_a_document_ocr_cannot_read_is_refused(
    data: bytes, media_type: str, pages: tuple[int, ...]
) -> None:
    with pytest.raises(ValueError, match=r"\w"):
        OcrRequest(data, media_type, pages)
