"""`/v1/files*` in the cabinet's contract and support's `/v1/admin/users/{id}/files*` (step 4)."""

import uuid

from shosai.core.kernel.homes import Home
from shosai.features.files.channels.http.admin_files import build_admin_files_router
from shosai.features.files.channels.http.files import build_files_router, build_folders_router
from shosai.features.identity.contracts import ADMIN_COOKIE
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.billing.catalogue_bench import ADMIN_SESSION
from tests.features.files.file_bench import EDGE, FileBench
from tests.features.files.upload_bench import person

# Поля из file-manager/domain/contract.ts кабинета.
CABINET_FILE = {
    "id", "name", "kind", "content_type", "size_bytes", "folder_id", "modified_at", "starred",
    "leo_readable", "leo",
}  # fmt: skip
CABINET_FOLDER = {"id", "name", "updated_at", "leo"}


async def test_the_file_manager_answers_in_the_cabinet_s_shape(file_bench: FileBench) -> None:
    who = person(Home.RU, uuid.uuid4())
    routers = (
        build_files_router((file_bench.manager, file_bench.downloads), file_bench.ports),
        build_folders_router(file_bench.folders, file_bench.ports),
        build_admin_files_router(file_bench.hidden, file_bench.ports),
    )
    app = build_probe_app(extra=routers).app
    upload_id = await file_bench.uploaded(who, "Plan.pdf", b"%PDF" * 50)
    headers = {"Authorization": f"Bearer person:{who.user_id}:{Home.RU.value}"}
    async with client_of(app) as http:
        made = await http.post("/v1/files", json={"upload_ids": [str(upload_id)]}, headers=headers)
        folder = (
            await http.post("/v1/files/folders", json={"name": " Projects "}, headers=headers)
        ).json()
        moved = await http.patch(
            f"/v1/files/{upload_id}",
            json={"folder_id": folder["id"], "starred": True},
            headers=headers,
        )
        rooted = await http.patch(
            f"/v1/files/{upload_id}", json={"folder_id": None}, headers=headers
        )
        copied = await http.post(f"/v1/files/{upload_id}/copy", headers=headers)
        listed = (await http.get("/v1/files", headers=headers)).json()
        link = await http.get(f"/v1/files/{upload_id}/download", headers=headers)
        bad_name = await http.patch(f"/v1/files/{upload_id}", json={"name": "a/b"}, headers=headers)
        unknown = await http.patch(f"/v1/files/{upload_id}", json={"tags": []}, headers=headers)
        deleted = await http.delete(f"/v1/files/{upload_id}", headers=headers)
        gone = await http.get(f"/v1/files/{upload_id}/download", headers=headers)
        anonymous = await http.get("/v1/files")
        support = f"/v1/admin/users/{who.user_id}/files"
        refused = await http.get(support, params={"home": "ru"})
        http.cookies.set(ADMIN_COOKIE, ADMIN_SESSION)
        hidden = (await http.get(support, params={"home": "ru"})).json()
        restored = await http.post(f"{support}/{upload_id}/restore", json={"home": "ru"})
        again = await http.post(f"{support}/{upload_id}/restore", json={"home": "ru"})
        http.cookies.clear()
        after = (await http.get("/v1/files", headers=headers)).json()

    [item] = made.json()["files"]
    assert (made.status_code, set(item), item["kind"], item["leo"]) == (
        201,
        CABINET_FILE,
        "pdf",
        None,
    )
    assert (folder["name"], set(folder)) == ("Projects", CABINET_FOLDER)
    assert (moved.json()["folder_id"], moved.json()["starred"]) == (folder["id"], True)
    assert rooted.json()["folder_id"] is None
    assert (copied.status_code, copied.json()["name"]) == (201, "Plan (2).pdf")
    assert {f["id"] for f in listed["files"]} == {str(upload_id), copied.json()["id"]}
    assert [set(f) for f in listed["folders"]] == [CABINET_FOLDER]
    assert link.status_code == 200
    assert link.json()["url"].startswith(f"{EDGE}/ru/")
    assert (bad_name.status_code, bad_name.json()["error"]["code"]) == (422, "name_slash")
    assert unknown.status_code == 422
    assert (deleted.status_code, gone.status_code, anonymous.status_code) == (204, 404, 401)
    assert refused.status_code in {401, 403}
    assert [f["id"] for f in hidden["files"]] == [str(upload_id)]
    assert (restored.status_code, again.status_code) == (204, 404)
    assert str(upload_id) in {f["id"] for f in after["files"]}


async def test_leo_s_switches_and_reindex_answer_in_the_cabinet_s_shape(
    file_bench: FileBench,
) -> None:
    who = person(Home.EU, uuid.uuid4())
    file_bench.uploads.plan.knowledge_base_mb = 1
    routers = (
        build_files_router((file_bench.manager, file_bench.downloads), file_bench.ports),
        build_folders_router(file_bench.folders, file_bench.ports),
    )
    app = build_probe_app(extra=routers).app
    small = await file_bench.uploaded(who, "Notes.txt", b"notes" * 20)
    large = await file_bench.uploaded(who, "Report.pdf", b"%PDF" * 300_000)
    headers = {"Authorization": f"Bearer person:{who.user_id}:{Home.EU.value}"}
    async with client_of(app) as http:
        made = await http.post(
            "/v1/files", json={"upload_ids": [str(small)], "leo": True}, headers=headers
        )
        await http.post("/v1/files", json={"upload_ids": [str(large)]}, headers=headers)
        unused = await http.post(f"/v1/files/{large}/reindex", headers=headers)
        over = await http.patch(f"/v1/files/{large}", json={"leo": True}, headers=headers)
        folder = (
            await http.post("/v1/files/folders", json={"name": "Leo"}, headers=headers)
        ).json()
        switched = await http.patch(
            f"/v1/files/folders/{folder['id']}", json={"leo": True}, headers=headers
        )
        renamed = await http.patch(
            f"/v1/files/folders/{folder['id']}", json={"name": "Read"}, headers=headers
        )
        reread = await http.post(f"/v1/files/{small}/reindex", headers=headers)

    [item] = made.json()["files"]
    assert (made.status_code, item["leo"]["via"], item["leo"]["status"]) == (201, "file", "queued")
    assert (unused.status_code, unused.json()["error"]["code"]) == (409, "leo_not_used")
    assert (over.status_code, over.json()["error"]["code"]) == (409, "leo_limit")
    assert over.json()["error"]["params"] == {"limit_bytes": 1024**2}
    assert (switched.json()["leo"], renamed.json()["name"], renamed.json()["leo"]) == (
        True,
        "Read",
        True,
    )
    assert (reread.status_code, reread.json()["leo"]["status"]) == (200, "queued")
