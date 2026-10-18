"""`/v1/me/uploads*` and the bucket rules (files step 3)."""

import uuid
from collections.abc import Mapping

import httpx
import pytest

from shosai.core.kernel.homes import Home
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.contracts import ENTITLEMENTS
from shosai.features.files.channels.bucket_rules import (
    apply_bucket_rules,
    cabinet_origins,
    cors_rules,
    lifecycle_rules,
)
from shosai.features.files.channels.http.uploads import build_uploads_router
from shosai.features.identity.contracts import AUTHENTICATOR
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.billing.people_bench import BearerOfTheTest
from tests.features.files.upload_bench import UploadBench
from tests.harness.shared_services import SlotBucket

ORIGIN = "https://shosai.tech"


async def test_an_upload_runs_through_its_routes(upload_bench: UploadBench) -> None:
    user_id = uuid.uuid4()
    ports = PortDirectory()
    ports.install([AUTHENTICATOR.bind(BearerOfTheTest()), ENTITLEMENTS.bind(upload_bench.plan)])
    app = build_probe_app(extra=(build_uploads_router(upload_bench.service, ports),)).app
    headers = {"Authorization": f"Bearer person:{user_id}:{Home.EU.value}"}
    body = {"purpose": "file_manager", "filename": "Plan.pdf", "content_type": "application/pdf",
            "size_bytes": 300}  # fmt: skip
    async with client_of(app) as http, httpx.AsyncClient() as bucket:
        created = (await http.post("/v1/me/uploads", json=body, headers=headers)).json()
        [part] = created["parts"]
        stored = await bucket.put(part["url"], content=b"p" * 300, headers=part["headers"])
        read = (await http.get(f"/v1/me/uploads/{created['id']}", headers=headers)).json()
        done = await http.post(f"/v1/me/uploads/{created['id']}/complete", headers=headers)
        cancelled = await http.delete(f"/v1/me/uploads/{created['id']}", headers=headers)
        anonymous = await http.post("/v1/me/uploads", json=body)
        wrong = await http.post(
            "/v1/me/uploads", json={**body, "purpose": "unknown"}, headers=headers
        )

    assert (created["state"], part["number"], part["size_bytes"]) == ("pending", 1, 300)
    assert stored.status_code == 200
    assert (read["done_parts"], read["parts"]) == ([1], [])
    assert (done.status_code, done.json()["state"]) == (200, "ready")
    assert cancelled.status_code == 204
    assert (anonymous.status_code, wrong.status_code) == (401, 422)


def test_the_rules_abort_incomplete_uploads_expire_transient_objects_and_allow_the_cabinet() -> (
    None
):
    rules = {rule["ID"]: rule for rule in lifecycle_rules()["Rules"]}

    assert rules["abort-incomplete-multipart"]["AbortIncompleteMultipartUpload"] == {
        "DaysAfterInitiation": 1
    }
    assert rules["expire-transient"]["Filter"] == {"Prefix": "transient/"}
    assert rules["expire-transient"]["Expiration"] == {"Days": 3}
    [cors] = cors_rules([ORIGIN])["CORSRules"]
    assert (cors["AllowedOrigins"], cors["ExposeHeaders"]) == ([ORIGIN], ["ETag"])
    with pytest.raises(ValueError, match="PUBLIC_BASE_URL"):
        cors_rules([])


def test_the_cabinet_s_origin_is_the_public_address_s_and_a_dev_server_joins_it() -> None:
    assert cabinet_origins("https://shosai.tech/", []) == [ORIGIN]
    assert cabinet_origins("https://shosai.tech/app", ["http://localhost:3000", ORIGIN]) == [
        ORIGIN,
        "http://localhost:3000",
    ]


async def test_the_rules_land_on_a_bucket_and_a_repeat_changes_nothing(
    buckets: Mapping[Home, SlotBucket],
) -> None:
    bucket = buckets[Home.RU]

    await apply_bucket_rules(bucket.client, bucket.bucket, [ORIGIN])
    await apply_bucket_rules(bucket.client, bucket.bucket, [ORIGIN])
    lifecycle = await bucket.client.get_bucket_lifecycle_configuration(Bucket=bucket.bucket)

    assert {rule["ID"] for rule in lifecycle["Rules"]} >= {
        "abort-incomplete-multipart",
        "expire-transient",
    }
