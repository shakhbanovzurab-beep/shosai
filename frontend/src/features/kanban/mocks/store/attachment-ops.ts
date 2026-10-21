import { findFile } from "@/features/file-manager/mocks/demo-store";
import { claimUpload } from "@/features/file-manager/mocks/demo-uploads";
import { isProblem } from "@/features/file-manager/mocks/problems";

import type { KanbanProblem } from "../../domain/problems";
import {
  ATTACHMENTS_MAX,
  type Attachment,
  type AttachmentCreate,
  type DownloadLink,
} from "../../domain/tasks-contract";
import { gradientPreview, ME_PERSON } from "../seed/builders";
import { fail, type Outcome, ok } from "./outcome";
import { demo, now, touchTask } from "./state";
import type { StoredTask } from "./types";

/*
 * Вложения задачи (KG-D3): загрузка с назначением `task_attachment` или копия файла File Manager, разделяющая
 * его объект (FL-D4). Байтов в демо нет: у картинки превью — градиент.
 */

const LINK_MS = 15 * 60_000;
const PREVIEWS = [
  ["#0ea5e9", "#22c55e"],
  ["#a855f7", "#ec4899"],
  ["#f59e0b", "#ef4444"],
];

function attachmentOf(name: string, contentType: string, size: number): Attachment {
  const image = /^image\/(png|jpeg|webp|gif)$/.test(contentType);
  const [from, to] = PREVIEWS[size % PREVIEWS.length];
  return {
    id: crypto.randomUUID(),
    name,
    content_type: contentType,
    size_bytes: size,
    image,
    preview_url: image ? gradientPreview(from, to) : null,
    added_by: ME_PERSON,
    added_at: now(),
  };
}

function bytesFor(request: AttachmentCreate): Attachment | KanbanProblem {
  if ("file_id" in request) {
    const file = findFile(request.file_id);
    return file ? attachmentOf(file.name, file.content_type, file.size_bytes) : "file_not_found";
  }
  const upload = claimUpload(request.upload_id, "task_attachment");
  if (isProblem(upload)) return "upload_not_claimable";
  return attachmentOf(upload.filename, upload.content_type, upload.size_bytes);
}

export function createAttachment(task: StoredTask, request: AttachmentCreate): Outcome<Attachment> {
  if (task.jira) return fail("jira_unsupported");
  const d = demo();
  const list = d.attachments.get(task.id) ?? [];
  if (list.length >= ATTACHMENTS_MAX) return fail("attachments_full");
  const attachment = bytesFor(request);
  if (typeof attachment === "string") return fail(attachment);
  d.attachments.set(task.id, [...list, attachment]);
  task.updated_at = now();
  touchTask(task.id);
  return ok(attachment);
}

export function downloadLink(task: StoredTask, id: string): Outcome<DownloadLink> {
  const attachment = demo()
    .attachments.get(task.id)
    ?.find((a) => a.id === id);
  if (!attachment) return fail("attachment_not_found");
  const expires_at = new Date(Date.now() + LINK_MS).toISOString();
  return ok({ url: `/demo-task-files/${encodeURIComponent(task.id)}/${encodeURIComponent(id)}`, expires_at });
}

export function deleteAttachment(task: StoredTask, id: string): Outcome<null> {
  const d = demo();
  const list = d.attachments.get(task.id) ?? [];
  if (!list.some((a) => a.id === id)) return fail("attachment_not_found");
  d.attachments.set(
    task.id,
    list.filter((a) => a.id !== id),
  );
  if (task.cover_attachment_id === id) task.cover_attachment_id = null;
  task.updated_at = now();
  touchTask(task.id);
  return ok(null);
}

/** Имя вложения для демо-«скачивания». */
export const attachmentName = (taskId: string, id: string) =>
  demo()
    .attachments.get(taskId)
    ?.find((a) => a.id === id)?.name ?? null;
