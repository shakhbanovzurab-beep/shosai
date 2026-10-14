"""`/email/{name}`: the layout's and the draft's images from a fixed list, cached long."""

from redis.asyncio import Redis

from tests.core.email.test_link_routes import link_app
from tests.harness.database_access import DatabaseAccess

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


async def test_the_icon_is_served_with_long_caching_and_its_tag(
    homes: DatabaseAccess, valkey: Redis
) -> None:
    async with link_app(homes.transactions, valkey) as app:
        icon = await app.http.get("/email/shosai-icon.png")
        again = await app.http.get(
            "/email/shosai-icon.png", headers={"If-None-Match": icon.headers["ETag"]}
        )

    assert icon.status_code == 200
    assert icon.headers["Content-Type"] == "image/png"
    assert icon.headers["Cache-Control"] == "public, max-age=2592000"
    assert icon.content.startswith(PNG_SIGNATURE)
    assert again.status_code == 304
    assert again.content == b""


async def test_the_draft_images_of_mail_already_sent_are_kept(
    homes: DatabaseAccess, valkey: Redis
) -> None:
    async with link_app(homes.transactions, valkey) as app:
        found = [
            await app.http.get(f"/email/{name}")
            for name in ("apple.png", "windows.png", "hazard.png")
        ]

    assert [image.status_code for image in found] == [200, 200, 200]
    assert all(image.content.startswith(PNG_SIGNATURE) for image in found)


async def test_a_name_outside_the_list_is_not_found(homes: DatabaseAccess, valkey: Redis) -> None:
    async with link_app(homes.transactions, valkey) as app:
        answers = [
            await app.http.get(path)
            for path in ("/email/logo.svg", "/email/..%2F..%2Fpyproject.toml", "/email/assets")
        ]

    assert [answer.status_code for answer in answers] == [404, 404, 404]
    assert answers[0].json()["error"]["code"] == "not_found"
