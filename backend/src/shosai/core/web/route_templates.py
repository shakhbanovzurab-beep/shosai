"""Route templates read from FastAPI's routing result, never by matching the path again.

After routing, FastAPI 0.142 leaves in the scope the route object as it was declared
(`scope["route"]`: an `APIRoute`, or any route of a mounted Starlette router) or only
the endpoint (`scope["endpoint"]`: a plain Starlette route such as the API docs, an
opaque mounted app). Neither carries the prefix the route is served under: a prefix of
`include_router`, of an outer router or of a mount. The full template of every route is
known at start through the public `iter_route_contexts`, so the app builds two maps
before its first request — route object → template, endpoint → template — and a request
only looks them up.

Prefixes, nested routers and mounts are supported. The start is refused only when the
scope cannot name one template: one route object or endpoint served under two templates
(the same router instance included twice — build it twice instead), or a kind of route
nobody has taught this module. Routes of `app.frontend()` are not listed by FastAPI and
count as unmatched.
"""

from collections.abc import Iterable, Mapping
from types import MappingProxyType

from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute, APIWebSocketRoute, iter_route_contexts
from starlette.routing import BaseRoute, Mount, Route, WebSocketRoute
from starlette.types import Scope

WEBSOCKET_ROUTES = (APIWebSocketRoute, WebSocketRoute)


class RouteLayoutError(Exception):
    """The scope could not name one template for some route; the message lists them."""


class RouteTemplates:
    """The full template of the route a request matched, looked up in O(1)."""

    def __init__(self, app: FastAPI) -> None:
        layout = _Layout()
        layout.walk(app.routes, prefix="", fastapi_routing=True)
        if layout.problems:
            message = "шаблон маршрута не восстановить по scope:\n" + "\n".join(layout.problems)
            raise RouteLayoutError(message)
        # Ключи — id объектов; кортеж держит сами объекты, чтобы id не освободились.
        self._objects = tuple(layout.objects)
        self._by_route: Mapping[int, str] = MappingProxyType(layout.by_route)
        self._by_endpoint: Mapping[int, str] = MappingProxyType(layout.by_endpoint)

    def of(self, scope: Scope) -> str | None:
        """`/v1/items/{item_id}` as served, converters included; None when nothing matched."""
        route = scope.get("route")
        if route is not None and (template := self._by_route.get(id(route))) is not None:
            return template
        endpoint = scope.get("endpoint")
        return None if endpoint is None else self._by_endpoint.get(id(endpoint))


class _Layout:
    """Walks the route tree once and records where each route object is served."""

    def __init__(self) -> None:
        self.by_route: dict[int, str] = {}
        self.by_endpoint: dict[int, str] = {}
        self.objects: list[object] = []
        self.problems: list[str] = []

    def walk(self, routes: Iterable[BaseRoute], prefix: str, *, fastapi_routing: bool) -> None:
        # FastAPI кладёт в scope["route"] только APIRoute; Starlette Router — любой маршрут.
        for context in iter_route_contexts(list(routes)):
            route = context.original_route
            template = prefix + (context.path or "")
            if isinstance(route, WEBSOCKET_ROUTES):
                continue
            if isinstance(route, Mount):
                self._mount(route, template, fastapi_routing=fastapi_routing)
            elif isinstance(route, APIRoute) or (isinstance(route, Route) and not fastapi_routing):
                self._record(self.by_route, route, template)
            elif isinstance(route, Route):
                self._record(self.by_endpoint, route.endpoint, template)
            else:
                self.problems.append(f"{template}: неизвестный вид маршрута {type(route).__name__}")

    def _mount(self, mount: Mount, template: str, *, fastapi_routing: bool) -> None:
        inner = mount.routes
        if inner:
            # Маршруты подприложения: шаблон — путь монтирования плюс их собственный.
            routing = isinstance(mount.app, FastAPI | APIRouter)
            self.walk(inner, template, fastapi_routing=routing)
            return
        # Непрозрачное приложение: FastAPI оставляет в scope только его как endpoint,
        # Starlette Router — сам Mount как route. Запись идёт туда, где её найдут.
        if fastapi_routing:
            self._record(self.by_endpoint, mount.app, template)
        else:
            self._record(self.by_route, mount, template)

    def _record(self, mapping: dict[int, str], target: object, template: str) -> None:
        known = mapping.get(id(target))
        if known is not None and known != template:
            self.problems.append(
                f"{template}: тот же объект уже обслуживается как {known}; "
                "подключите отдельный экземпляр роутера"
            )
            return
        mapping[id(target)] = template
        self.objects.append(target)
