"""Mistral OCR: scans and images of documents read to Markdown, page by page.

Facts from Mistral's documentation (OCR endpoint, models and pricing, read on 2026-10-13),
and the draft's lessons:

- `POST /v1/ocr` with `model` and `document`; a PDF goes as `{type: document_url,
  document_url}`, an image as `{type: image_url, image_url}` — the wrong type answers 422
- the document goes as a `data:` URL, not a link: the bucket is private, and a presigned
  link would hand a person's document to the internet
- `pages` (from 0) limits a PDF; the answer is `pages[] {index, markdown, dimensions}` and
  `usage_info {pages_processed}`, the billed pages, with no money in it
- OCR 4.1 costs $4 per 1000 pages; the model is pinned, never `mistral-ocr-latest`
"""

import base64
from decimal import Decimal
from typing import Final

import httpx

from shosai.core.ai.adapters.http_calls import Json, call_json
from shosai.core.ai.calls import ModelRef, Provider
from shosai.core.ai.documents import OcrPage, OcrPages, OcrRequest
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.results import Unit, Usage

MISTRAL_API: Final = "https://api.mistral.ai/v1"
# Скан в сотню страниц читается минутами (черновик: 180 с хватало).
OCR_TIMEOUT: Final = httpx.Timeout(connect=10.0, read=180.0, write=60.0, pool=5.0)


def mistral_client(api_key: str, base_url: str = MISTRAL_API) -> httpx.AsyncClient:
    """The process's client of the Mistral API."""
    return httpx.AsyncClient(
        base_url=base_url.rstrip("/") + "/",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=OCR_TIMEOUT,
        limits=httpx.Limits(max_connections=16, max_keepalive_connections=4, keepalive_expiry=60),
    )


def ocr_body(model: str, request: OcrRequest) -> Json:
    """The body of `/ocr`: the document inline, as a data URL of its own type."""
    data_url = f"data:{request.media_type};base64,{base64.b64encode(request.data).decode('ascii')}"
    kind = "document_url" if request.media_type == "application/pdf" else "image_url"
    body: Json = {
        "model": model,
        "document": {"type": kind, kind: data_url},
        "include_image_base64": False,
    }
    if request.pages:
        body["pages"] = list(request.pages)
    return body


def page_of(raw: object) -> OcrPage:
    """One page of the answer."""
    if not isinstance(raw, dict) or not isinstance(raw.get("index"), int):
        raise AiCallError(AiFailure.PROVIDER_ERROR)
    dimensions = raw.get("dimensions")
    size = dimensions if isinstance(dimensions, dict) else {}
    width, height = size.get("width"), size.get("height")
    return OcrPage(
        index=raw["index"],
        markdown=str(raw.get("markdown") or ""),
        width=width if isinstance(width, int) else None,
        height=height if isinstance(height, int) else None,
    )


def pages_of(answer: Json, model: ModelRef) -> OcrPages:
    """The pages read and the pages billed."""
    pages = answer.get("pages")
    usage = answer.get("usage_info")
    billed = usage.get("pages_processed") if isinstance(usage, dict) else None
    if not isinstance(pages, list) or not isinstance(billed, int) or billed < 0:
        raise AiCallError(AiFailure.PROVIDER_ERROR)
    read = tuple(sorted((page_of(page) for page in pages), key=lambda page: page.index))
    return OcrPages(pages=read, model=model, usage=Usage(units=Decimal(billed), unit=Unit.PAGE))


class MistralOcr:
    """Reads documents with Mistral's OCR model."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def ocr(self, model: ModelRef, request: OcrRequest) -> OcrPages:
        """The document's pages as Markdown."""
        built = self._client.build_request("POST", "ocr", json=ocr_body(model.model, request))
        answer = await call_json(self._client, Provider.MISTRAL, built)
        return pages_of(answer, model)
