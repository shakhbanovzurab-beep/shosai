"""The public routes of a composed app as the route snapshot records them (§10, D1).

Each route is `"METHOD /path"`, a WebSocket route `"WS /path"` — the format of the D1
harness (`contracts/README.md`, "Produce the v2 artifacts").
"""

from fastapi import FastAPI
from fastapi.routing import APIRoute, APIWebSocketRoute, iter_route_contexts


def route_snapshot(app: FastAPI) -> list[str]:
    """Every HTTP and WebSocket route of the app, sorted."""
    keys: set[str] = set()
    for context in iter_route_contexts(app.routes):
        route = context.original_route
        if isinstance(route, APIWebSocketRoute):
            # FastAPI 0.142 не даёт контексту WebSocket-маршрута из подключённого роутера путь:
            # тогда путь — маршрута; роутеры WS подключаются без префикса.
            keys.add(f"WS {context.path or route.path}")
        elif isinstance(route, APIRoute):
            keys.update(f"{method} {context.path}" for method in context.methods or ())
    return sorted(keys)
