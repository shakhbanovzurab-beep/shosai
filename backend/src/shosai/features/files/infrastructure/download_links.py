"""Download links on Shosai's own address (ADR 0055 point 8; FL-D9).

A presigned GET of the home's bucket is rewritten to `{base}/{home}{path}?{query}`: the
edge strips `/{home}`, forwards the path and the signed query unchanged to that home's
bucket endpoint and adds `nosniff` and a sandbox to the bytes. The signature covers the
bucket's host, path and query, which the edge keeps. Without a base (local development)
the presigned link itself is answered.
"""

from urllib.parse import urlsplit

from shosai.core.kernel.homes import Home


def edge_link(presigned_url: str, home: Home, base: str | None) -> str:
    """The link the browser opens."""
    if base is None:
        return presigned_url
    parts = urlsplit(presigned_url)
    query = f"?{parts.query}" if parts.query else ""
    return f"{base.rstrip('/')}/{home.value}{parts.path}{query}"
