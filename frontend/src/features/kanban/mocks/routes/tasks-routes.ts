import { COMMENTS_PAGE_DEFAULT, COMMENTS_PAGE_MAX } from "../../domain/tasks-contract";
import { attachmentName, createAttachment, deleteAttachment, downloadLink } from "../store/attachment-ops";
import { commentOf, taskDetailOf } from "../store/present";
import { clearValue, putValue } from "../store/sticker-ops";
import { deleteTasks, patchTask } from "../store/task-ops";
import { commentsPage, createComment, deleteComment, editComment } from "../store/thread-ops";
import { bodyOf, json, type Params } from "./http";
import { answer, answerEmpty, withTask } from "./respond";
import { attachmentSchema, commentSchema, taskPatchSchema, tasksDeleteSchema, valueSchema } from "./task-schemas";

/* `/v1/tasks*`: задача, удаление пачкой, комментарии, вложения и значения полей (план tasks §3.3, §3.8). */

const sub = async (params: Promise<Record<string, string>>, key: string) => (await params)[key] ?? "";
const same = <T>(value: T) => value;

/** /v1/tasks/[id] */
export const taskRoute = {
  async GET(_request: Request, { params }: Params<"id">) {
    return withTask(params, (task) => json(taskDetailOf(task)));
  },
  async PATCH(request: Request, { params }: Params<"id">) {
    return withTask(params, async (task) => {
      const body = await bodyOf(request, taskPatchSchema);
      if ("refusal" in body) return body.refusal;
      return answer(patchTask(task, body.data), taskDetailOf);
    });
  },
  async DELETE(_request: Request, { params }: Params<"id">) {
    return withTask(params, (task) => answerEmpty(deleteTasks([task.id])));
  },
};

/** /v1/tasks/delete: пачка после Undo, все или ни одной. */
export const tasksDeleteRoute = {
  async POST(request: Request) {
    const body = await bodyOf(request, tasksDeleteSchema);
    if ("refusal" in body) return body.refusal;
    return answerEmpty(deleteTasks(body.data.task_ids));
  },
};

/** /v1/tasks/[id]/comments */
export const commentsRoute = {
  async GET(request: Request, { params }: Params<"id">) {
    return withTask(params, (task) => {
      const query = new URL(request.url).searchParams;
      const limit = Math.min(COMMENTS_PAGE_MAX, Math.max(1, Number(query.get("limit")) || COMMENTS_PAGE_DEFAULT));
      return json(commentsPage(task, query.get("cursor"), limit));
    });
  },
  async POST(request: Request, { params }: Params<"id">) {
    return withTask(params, async (task) => {
      const body = await bodyOf(request, commentSchema);
      if ("refusal" in body) return body.refusal;
      return answer(createComment(task, body.data.body, request.headers.get("idempotency-key")), commentOf, 201);
    });
  },
};

/** /v1/tasks/[id]/comments/[commentId]: править и удалять — только автору. */
export const commentRoute = {
  async PATCH(request: Request, { params }: Params<"id" | "commentId">) {
    return withTask(params, async (task) => {
      const body = await bodyOf(request, commentSchema);
      if ("refusal" in body) return body.refusal;
      return answer(editComment(task, await sub(params, "commentId"), body.data.body), commentOf);
    });
  },
  async DELETE(_request: Request, { params }: Params<"id" | "commentId">) {
    return withTask(params, async (task) => answerEmpty(deleteComment(task, await sub(params, "commentId"))));
  },
};

/** /v1/tasks/[id]/attachments */
export const attachmentsRoute = {
  async POST(request: Request, { params }: Params<"id">) {
    return withTask(params, async (task) => {
      const body = await bodyOf(request, attachmentSchema);
      if ("refusal" in body) return body.refusal;
      return answer(createAttachment(task, body.data), same, 201);
    });
  },
};

/** /v1/tasks/[id]/attachments/[attachmentId] */
export const attachmentRoute = {
  async DELETE(_request: Request, { params }: Params<"id" | "attachmentId">) {
    return withTask(params, async (task) => answerEmpty(deleteAttachment(task, await sub(params, "attachmentId"))));
  },
};

/** /v1/tasks/[id]/attachments/[attachmentId]/download */
export const attachmentDownloadRoute = {
  async GET(_request: Request, { params }: Params<"id" | "attachmentId">) {
    return withTask(params, async (task) => answer(downloadLink(task, await sub(params, "attachmentId")), same));
  },
};

/** /demo-task-files/[id]/[attachmentId]: байтов в демо нет, «скачивание» — короткий текст об этом. */
export const demoTaskFileRoute = {
  async GET(_request: Request, { params }: Params<"id" | "attachmentId">) {
    const name = attachmentName(await sub(params, "id"), await sub(params, "attachmentId"));
    if (name === null) return new Response(null, { status: 404 });
    return new Response(`Demo attachment: ${name}\n`, {
      headers: { "content-type": "text/plain; charset=utf-8", "content-disposition": "attachment" },
    });
  },
};

/** /v1/tasks/[id]/values/[stickerId] */
export const valueRoute = {
  async PUT(request: Request, { params }: Params<"id" | "stickerId">) {
    return withTask(params, async (task) => {
      const body = await bodyOf(request, valueSchema);
      if ("refusal" in body) return body.refusal;
      return answer(putValue(task, await sub(params, "stickerId"), body.data), same);
    });
  },
  async DELETE(_request: Request, { params }: Params<"id" | "stickerId">) {
    return withTask(params, async (task) => answerEmpty(clearValue(task, await sub(params, "stickerId"))));
  },
};
