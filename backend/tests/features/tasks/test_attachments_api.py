"""A task's attachments and cover answer as the cabinet's mocks do (tasks plan §3.13)."""

import uuid
from io import BytesIO

import httpx
from PIL import Image

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.tasks.infrastructure.attachment_records import TaskAttachmentRecord
from tests.features.tasks.holding_bench import EDGE
from tests.features.tasks.task_bench import TaskBench


def code_of(answer: httpx.Response) -> str:
    """The refusal's code in the platform's envelope."""
    return str(answer.json()["error"]["code"])


def png() -> bytes:
    """A landscape PNG."""
    out = BytesIO()
    Image.new("RGB", (1280, 720), (240, 160, 40)).save(out, format="PNG")
    return out.getvalue()


async def attach(bench: TaskBench, who: uuid.UUID, task: uuid.UUID, body: object) -> httpx.Response:
    """POST an attachment."""
    return await bench.call(who, "POST", f"/v1/tasks/{task}/attachments", body)


async def test_a_file_manager_file_is_attached_as_a_copy_and_a_cover_must_be_an_image(
    task_bench: TaskBench,
) -> None:
    me = uuid.uuid4()
    task = await task_bench.task(me)
    file_id, _ = await task_bench.files.file(me, "Brand exports.zip", b"zip bytes")

    reply = await attach(task_bench, me, task, {"file_id": str(file_id)})
    cover = await task_bench.call(
        me, "PATCH", f"/v1/tasks/{task}", {"cover_attachment_id": reply.json()["id"]}
    )

    assert reply.status_code == 201
    assert set(reply.json()) == {
        "id", "name", "content_type", "size_bytes", "image", "preview_url", "added_by", "added_at",
    }  # fmt: skip
    assert (reply.json()["name"], reply.json()["image"]) == ("Brand exports.zip", False)
    assert reply.json()["added_by"]["user_id"] == str(me)
    assert (cover.status_code, code_of(cover)) == (409, "cover_not_image")
    assert await task_bench.files.used(me) == 18


async def test_an_image_gets_its_preview_on_the_cover_and_in_the_panel(
    task_bench: TaskBench,
) -> None:
    me = uuid.uuid4()
    task = await task_bench.task(me)
    upload = await task_bench.files.uploaded(me, png(), "image/png")

    made = (await attach(task_bench, me, task, {"upload_id": str(upload)})).json()
    before = (await task_bench.call(me, "GET", f"/v1/tasks/{task}")).json()
    await task_bench.files.make_previews()
    await task_bench.call(me, "PATCH", f"/v1/tasks/{task}", {"cover_attachment_id": made["id"]})
    detail = (await task_bench.call(me, "GET", f"/v1/tasks/{task}")).json()
    (item,) = (await task_bench.call(me, "GET", "/v1/tasks")).json()["items"]

    assert (made["image"], made["preview_url"]) == (True, None)
    assert before["attachments"][0]["preview_url"] is None
    assert detail["cover"]["attachment_id"] == made["id"]
    assert detail["cover"]["preview_url"].startswith(EDGE)
    assert detail["attachments"][0]["preview_url"].startswith(EDGE)
    assert (item["attachment_count"], item["cover"]["attachment_id"]) == (1, made["id"])


async def test_removing_the_covers_attachment_removes_the_cover_and_gives_its_bytes_back(
    task_bench: TaskBench,
) -> None:
    me = uuid.uuid4()
    task = await task_bench.task(me)
    board = await task_bench.board(me)
    await task_bench.place(me, task, board)
    upload = await task_bench.files.uploaded(me, png(), "image/png")
    made = (await attach(task_bench, me, task, {"upload_id": str(upload)})).json()
    await task_bench.call(me, "PATCH", f"/v1/tasks/{task}", {"cover_attachment_id": made["id"]})
    used = await task_bench.files.used(me)

    gone = await task_bench.call(me, "DELETE", f"/v1/tasks/{task}/attachments/{made['id']}")
    again = await task_bench.call(me, "DELETE", f"/v1/tasks/{task}/attachments/{made['id']}")
    detail = (await task_bench.call(me, "GET", f"/v1/tasks/{task}")).json()

    assert used == len(png())
    assert (gone.status_code, again.status_code, code_of(again)) == (
        204, 404, "attachment_not_found",
    )  # fmt: skip
    assert (detail["cover"], detail["attachment_count"], detail["attachments"]) == (None, 0, [])
    assert await task_bench.files.used(me) == 0
    assert await task_bench.revision(me, board[0]) == 4


async def test_a_repeated_upload_is_one_attachment_and_anything_else_is_refused(
    task_bench: TaskBench,
) -> None:
    me, stranger = uuid.uuid4(), uuid.uuid4()
    task, other = await task_bench.task(me), await task_bench.task(me)
    upload = await task_bench.files.uploaded(me, b"%PDF-1.7", "application/pdf")
    theirs, _ = await task_bench.files.file(stranger, "Чужое.pdf", b"secret")

    first = await attach(task_bench, me, task, {"upload_id": str(upload)})
    again = await attach(task_bench, me, task, {"upload_id": str(upload)})
    elsewhere = await attach(task_bench, me, other, {"upload_id": str(upload)})
    unknown = await attach(task_bench, me, task, {"upload_id": str(uuid.uuid4())})
    unreadable = await attach(task_bench, me, task, {"file_id": str(theirs)})
    both = await attach(task_bench, me, task, {"upload_id": str(upload), "file_id": str(theirs)})
    foreign = await attach(task_bench, stranger, task, {"upload_id": str(upload)})

    assert again.json()["id"] == first.json()["id"]
    refusals = (elsewhere, unknown, unreadable, both, foreign)
    assert [(a.status_code, code_of(a)) for a in refusals] == [
        (409, "upload_not_claimable"), (409, "upload_not_claimable"), (404, "file_not_found"),
        (422, "validation_error"), (404, "task_not_found"),
    ]  # fmt: skip
    detail = (await task_bench.call(me, "GET", f"/v1/tasks/{task}")).json()
    assert detail["attachment_count"] == 1


async def test_a_task_holds_fifty_attachments(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    task = await task_bench.task(me)
    async with task_bench.homes.transactions.begin(TenancyScope(Home.EU, me)) as session:
        session.add_all(
            TaskAttachmentRecord(
                id=uuid.uuid4(), task_id=task, user_id=me, held_object_id=uuid.uuid4(),
                name="a.pdf", content_type="application/pdf", size_bytes=1, image=False,
                added_by=me,
            )
            for _ in range(50)
        )  # fmt: skip
    upload = await task_bench.files.uploaded(me, b"one more", "application/pdf")

    full = await attach(task_bench, me, task, {"upload_id": str(upload)})

    assert (full.status_code, code_of(full)) == (409, "attachments_full")
    assert await task_bench.files.used(me) == 0


async def test_a_workspace_task_and_a_jira_task_take_no_attachments(task_bench: TaskBench) -> None:
    me, org = uuid.uuid4(), uuid.uuid4()
    await task_bench.workspace(org, me)
    shared = await task_bench.task(me, org)
    jira = await task_bench.task(me, source="jira")
    upload = await task_bench.files.uploaded(me, b"bytes", "application/pdf")

    in_workspace = await attach(task_bench, me, shared, {"upload_id": str(upload)})
    on_jira = await attach(task_bench, me, jira, {"upload_id": str(upload)})
    cover = await task_bench.call(me, "PATCH", f"/v1/tasks/{jira}", {"cover_attachment_id": None})

    assert (in_workspace.status_code, code_of(in_workspace)) == (403, "storage_not_included")
    assert (on_jira.status_code, code_of(on_jira)) == (409, "jira_unsupported")
    assert (cover.status_code, code_of(cover)) == (409, "jira_unsupported")


async def test_a_copied_files_object_stays_with_the_file_and_a_deleted_task_gives_its_bytes_back(
    task_bench: TaskBench,
) -> None:
    me = uuid.uuid4()
    task = await task_bench.task(me)
    file_id, key = await task_bench.files.file(me, "Отчёт.pdf", b"report")
    copy = (await attach(task_bench, me, task, {"file_id": str(file_id)})).json()
    upload = await task_bench.files.uploaded(me, b"own bytes", "application/pdf")
    await attach(task_bench, me, task, {"upload_id": str(upload)})
    charged = await task_bench.files.used(me)

    await task_bench.call(me, "DELETE", f"/v1/tasks/{task}/attachments/{copy['id']}")
    kept = await task_bench.files.exists(key)
    await task_bench.call(me, "DELETE", f"/v1/tasks/{task}")

    assert charged == 6 + 6 + 9
    assert kept
    assert await task_bench.files.used(me) == 6
    assert not await task_bench.files.exists(f"u/{me}/h/{upload}")


async def test_a_download_is_a_short_link_on_shosais_address(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    task = await task_bench.task(me)
    upload = await task_bench.files.uploaded(me, b"%PDF-1.7", "application/pdf")
    made = (await attach(task_bench, me, task, {"upload_id": str(upload)})).json()

    link = await task_bench.call(me, "GET", f"/v1/tasks/{task}/attachments/{made['id']}/download")
    missing = await task_bench.call(
        me, "GET", f"/v1/tasks/{task}/attachments/{uuid.uuid4()}/download"
    )

    assert link.json()["url"].startswith(EDGE)
    assert set(link.json()) == {"url", "expires_at"}
    assert (missing.status_code, code_of(missing)) == (404, "attachment_not_found")
