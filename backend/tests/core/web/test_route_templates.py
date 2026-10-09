"""Route templates come from FastAPI's routing result for every layout a slice may use."""

import re
from pathlib import Path
from typing import Any

import pytest
from fastapi import APIRouter, FastAPI, WebSocket
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Host, Mount, Route, Router
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from shosai.core.web.route_templates import RouteLayoutError, RouteTemplates

CONVERTER = re.compile(r"\{(\w+):\w+\}")


def items_router() -> APIRouter:
    """A slice router declared without its outer prefix."""
    router = APIRouter(prefix="/items")

    @router.get("/{item_id}")
    async def read_item(item_id: str) -> dict[str, str]:
        """An item."""
        return {"id": item_id}

    @router.get("/{item_id}/files/{name:path}")
    async def read_file(item_id: str, name: str) -> dict[str, str]:
        """A file of an item; the template has a converter."""
        return {"id": item_id, "name": name}

    return router


async def plain_page(_request: Request) -> Response:
    """A plain Starlette endpoint."""
    return PlainTextResponse("ok")


async def opaque_app(scope: Scope, receive: Receive, send: Send) -> None:
    """A mounted ASGI app without routes of its own."""
    await PlainTextResponse("opaque")(scope, receive, send)


def layered_app(frontend: Path) -> FastAPI:
    """Every layout a slice or composition may use, in one app."""
    outer = APIRouter(prefix="/v1/outer")
    outer.include_router(items_router(), prefix="/nested")
    sub = FastAPI()
    sub.include_router(items_router())
    app = FastAPI()
    app.include_router(items_router(), prefix="/v1")
    app.include_router(outer)
    app.add_route("/plain/{page}", plain_page)
    app.mount("/sub", sub)
    app.mount("/router", Router(routes=[Route("/r/{z}", plain_page), Mount("/deep", opaque_app)]))
    app.mount("/opaque", opaque_app)

    @app.websocket("/v1/ws/echo")
    async def echo(websocket: WebSocket) -> None:
        """A WebSocket route; the HTTP templates leave it to the WebSocket layer."""
        await websocket.close()

    (frontend / "index.html").write_text("<html></html>", encoding="utf-8")
    (frontend / "app.js").write_text("1", encoding="utf-8")
    app.frontend("/", directory=str(frontend))
    return app


async def served(app: ASGIApp, method: str, path: str) -> Scope:
    """The scope as the boundary sees it after the app has answered."""
    scope: dict[str, Any] = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method,
        "scheme": "http", "path": path, "raw_path": path.encode(), "root_path": "",
        "query_string": b"", "headers": [(b"host", b"t"), (b"accept", b"text/html")],
        "client": ("127.0.0.1", 1), "server": ("t", 80),
    }  # fmt: skip

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(_message: Message) -> None:
        return None

    await app(scope, receive, send)
    return scope


SERVED = [
    ("GET", "/v1/items/7", "/v1/items/{item_id}"),
    ("POST", "/v1/items/7", "/v1/items/{item_id}"),
    ("GET", "/v1/items/7/files/a/b.txt", "/v1/items/{item_id}/files/{name:path}"),
    ("GET", "/v1/outer/nested/items/7", "/v1/outer/nested/items/{item_id}"),
    ("GET", "/plain/about", "/plain/{page}"),
    ("POST", "/plain/about", "/plain/{page}"),
    ("GET", "/openapi.json", "/openapi.json"),
    ("HEAD", "/docs", "/docs"),
    ("GET", "/sub/items/7", "/sub/items/{item_id}"),
    ("GET", "/sub/openapi.json", "/sub/openapi.json"),
    ("GET", "/router/r/9", "/router/r/{z}"),
    ("GET", "/router/deep/x/y", "/router/deep"),
    ("GET", "/opaque/anything/at/all", "/opaque"),
]
UNMATCHED = [
    ("GET", "/v1/missing"),
    ("GET", "/v1/items/7/"),
    ("GET", "/sub/missing"),
    ("GET", "/app.js"),
    ("GET", "/some/spa/page"),
]


@pytest.mark.parametrize(("method", "path", "template"), SERVED)
async def test_every_layout_resolves_to_the_template_it_is_served_under(
    tmp_path: Path, method: str, path: str, template: str
) -> None:
    app = layered_app(tmp_path)

    assert RouteTemplates(app).of(await served(app, method, path)) == template


@pytest.mark.parametrize(("method", "path"), UNMATCHED)
async def test_unmatched_paths_redirects_and_frontend_files_have_no_template(
    tmp_path: Path, method: str, path: str
) -> None:
    app = layered_app(tmp_path)

    assert RouteTemplates(app).of(await served(app, method, path)) is None


@pytest.mark.parametrize(
    "path", ["/v1/items/7", "/v1/items/7/files/a.txt", "/v1/outer/nested/items/7"]
)
async def test_the_template_is_the_http_route_fastapi_traces(tmp_path: Path, path: str) -> None:
    spans = InMemorySpanExporter()
    provider = TracerProvider(shutdown_on_exit=False)
    provider.add_span_processor(SimpleSpanProcessor(spans))
    app = layered_app(tmp_path)
    traced = FastAPI(telemetry={"tracer_provider": provider, "auto_configure": False})
    traced.mount("/", app)
    templates = RouteTemplates(app)

    template = templates.of(await served(traced, "GET", path))

    [span] = [s for s in spans.get_finished_spans() if s.name.startswith("GET /v1")]
    assert template is not None
    assert CONVERTER.sub(r"{\1}", template) == dict(span.attributes or {})["http.route"]


def test_one_router_instance_included_twice_stops_the_start() -> None:
    router = items_router()
    app = FastAPI()
    app.include_router(router, prefix="/v1")
    app.include_router(router, prefix="/v2")

    with pytest.raises(RouteLayoutError, match=r"/v2/items/\{item_id\}.*уже обслуживается как /v1"):
        RouteTemplates(app)


def test_the_same_router_built_twice_is_accepted() -> None:
    app = FastAPI()
    app.include_router(items_router(), prefix="/v1")
    app.include_router(items_router(), prefix="/v2")

    RouteTemplates(app)


def test_one_endpoint_under_two_plain_routes_stops_the_start() -> None:
    app = FastAPI()
    app.add_route("/a", plain_page)
    app.add_route("/b", plain_page)

    with pytest.raises(RouteLayoutError, match="уже обслуживается как /a"):
        RouteTemplates(app)


@pytest.mark.parametrize("nested", [False, True])
def test_an_unknown_kind_of_route_stops_the_start(*, nested: bool) -> None:
    host = Host("api.example", app=opaque_app)
    app = FastAPI()
    if nested:
        app.mount("/router", Router(routes=[host]))
    else:
        app.router.routes.append(host)

    with pytest.raises(RouteLayoutError, match="неизвестный вид маршрута Host"):
        RouteTemplates(app)
