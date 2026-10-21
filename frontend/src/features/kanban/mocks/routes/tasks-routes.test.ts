import { beforeEach, describe, expect, it } from "vitest";

import type { OwnedSticker } from "../../domain/stickers-contract";
import type { Attachment, Comment, CommentsPage, TaskDetail } from "../../domain/tasks-contract";
import { resetDemo } from "../store/state";
import {
  boardStickerRoute,
  boardStickersRoute,
  stickerRoute,
  stickersRoute,
  subtasksRoute,
} from "./subtasks-stickers-routes";
import {
  attachmentRoute,
  attachmentsRoute,
  commentRoute,
  commentsRoute,
  taskRoute,
  tasksDeleteRoute,
  valueRoute,
} from "./tasks-routes";
import { call, codeOf } from "./test-client";

const task = async (id: string) =>
  (await call(taskRoute, "GET", `/v1/tasks/${id}`, { params: { id } })).body as TaskDetail;
const patch = (id: string, body: object) => call(taskRoute, "PATCH", `/v1/tasks/${id}`, { params: { id }, body });

beforeEach(() => {
  resetDemo();
});

describe("a task's fields", () => {
  it("drops Leo's mark from the field the person changed, and only from it", async () => {
    await patch("w-pricing-deck", { due_on: "2026-12-01" });
    expect((await task("w-pricing-deck")).leo_fields).toEqual(["assignee", "priority"]);
  });

  it("clears a field sent as null and keeps a range inside its due day", async () => {
    expect((await patch("w-schema", { priority: null })).body).toMatchObject({ priority: null });
    const range = await patch("w-schema", { starts_on: "2099-01-02", due_on: "2099-01-01" });
    expect(range.status).toBe(422);
    expect(codeOf(range)).toBe("range_invalid");
  });

  it("gives a recurring task without a due day its first date", async () => {
    const reply = await patch("w-dark-charts", { recurrence: { every: "day" } });
    expect((reply.body as TaskDetail).due_on).not.toBeNull();
  });

  it("refuses a week with no day", async () => {
    const reply = await patch("w-dark-charts", { recurrence: { every: "week", weekdays: [] } });
    expect(reply.status).toBe(422);
  });

  it("deletes all of a batch or none", async () => {
    const reply = await call(tasksDeleteRoute, "POST", "/v1/tasks/delete", {
      body: { task_ids: ["w-dark-charts", "jira-WEB-1"] },
    });
    expect(codeOf(reply)).toBe("task_not_found");
    expect((await task("w-dark-charts")).id).toBe("w-dark-charts");
  });
});

describe("field values", () => {
  it("are the task's: off the board they stay with the task as its other values", async () => {
    await call(valueRoute, "PUT", "/v1/tasks/w-ai-summaries/values/st-estimate", {
      params: { id: "w-ai-summaries", stickerId: "st-estimate" },
      body: { number: 2 },
    });
    expect((await task("w-ai-summaries")).values["st-estimate"]).toEqual({ number: 2 });
    await call(boardStickerRoute, "DELETE", "/v1/boards/work/stickers/st-estimate", {
      params: { id: "work", stickerId: "st-estimate" },
    });
    const detail = await task("w-ai-summaries");
    expect(detail.values["st-estimate"]).toBeUndefined();
    expect(detail.other_values.map((v) => v.sticker.id)).toContain("st-estimate");
  });

  it("refuses a value of another kind", async () => {
    const reply = await call(valueRoute, "PUT", "/v1/tasks/w-schema/values/st-estimate", {
      params: { id: "w-schema", stickerId: "st-estimate" },
      body: { state_id: "type-bug" },
    });
    expect(codeOf(reply)).toBe("value_kind_mismatch");
  });

  it("a removed state clears the values that used it, and a field is reused on another board", async () => {
    await call(stickerRoute, "PATCH", "/v1/stickers/st-type", {
      params: { id: "st-type" },
      body: { states: [{ id: "type-feature", name: "Feature", color: "blue" }] },
    });
    expect((await task("w-sso-crash")).values["st-type"]).toBeUndefined();
    const placed = await call(boardStickersRoute, "POST", "/v1/boards/home/stickers", {
      params: { id: "home" },
      body: { sticker_id: "st-type" },
    });
    expect(placed.status).toBe(201);
    const owned = (await call(stickersRoute, "GET", "/v1/stickers")).body as { items: OwnedSticker[] };
    const type = owned.items.find((s) => s.id === "st-type");
    expect(type?.boards.map((b) => b.id)).toEqual(expect.arrayContaining(["work", "home"]));
  });
});

describe("subtasks, comments and attachments", () => {
  it("keeps a checklist in order", async () => {
    await call(subtasksRoute, "POST", "/v1/tasks/w-ai-summaries/subtasks", {
      params: { id: "w-ai-summaries" },
      body: { title: "Find long threads" },
    });
    const detail = await task("w-ai-summaries");
    expect(detail.subtasks.map((s) => s.title)).toEqual(["Find long threads"]);
    expect(detail.subtasks_total).toBe(1);
  });

  it("answers a repeated comment with the same comment, pages newest first, and lets only the author edit", async () => {
    const post = () =>
      call(commentsRoute, "POST", "/v1/tasks/w-schema/comments", {
        params: { id: "w-schema" },
        body: { body: "Indexes next" },
        headers: { "idempotency-key": "k-1" },
      });
    const first = (await post()).body as Comment;
    const second = (await post()).body as Comment;
    expect(second.id).toBe(first.id);
    const page = (
      await call(commentsRoute, "GET", "/v1/tasks/w-schema/comments?limit=2", { params: { id: "w-schema" } })
    ).body as CommentsPage;
    expect(page.items[0]?.id).toBe(first.id);
    expect(page.next_cursor).not.toBeNull();
    const foreign = await call(commentRoute, "PATCH", "/v1/tasks/w-schema/comments/w-schema-c1", {
      params: { id: "w-schema", commentId: "w-schema-c1" },
      body: { body: "Mine now" },
    });
    expect(codeOf(foreign)).toBe("not_comment_author");
  });

  it("attaches a File Manager file as a copy, and a cover must be an image", async () => {
    const reply = await call(attachmentsRoute, "POST", "/v1/tasks/w-csv-export/attachments", {
      params: { id: "w-csv-export" },
      body: { file_id: "f-brand-exports" },
    });
    expect(reply.status).toBe(201);
    const attachment = reply.body as Attachment;
    expect(attachment.name).toBe("Brand exports.zip");
    expect(codeOf(await patch("w-csv-export", { cover_attachment_id: attachment.id }))).toBe("cover_not_image");
  });

  it("removing the cover's attachment removes the cover", async () => {
    await call(attachmentRoute, "DELETE", "/v1/tasks/w-schema/attachments/w-schema-a1", {
      params: { id: "w-schema", attachmentId: "w-schema-a1" },
    });
    expect((await task("w-schema")).cover).toBeNull();
  });
});
