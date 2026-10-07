import { toast } from "sonner";

import { type AttachmentMeta, MAX_ATTACHMENT_BYTES, MAX_ATTACHMENTS } from "../domain/contract";

/** Keeps files within the limits, saying what was skipped. Only metadata is sent. */
export function addFiles(current: AttachmentMeta[], incoming: File[]): AttachmentMeta[] {
  const tooBig = incoming.filter((f) => f.size > MAX_ATTACHMENT_BYTES);
  if (tooBig.length > 0) toast.error(`Больше 20 МБ: ${tooBig.map((f) => f.name).join(", ")}`);
  const added = incoming
    .filter((f) => f.size <= MAX_ATTACHMENT_BYTES)
    .map((f) => ({ name: f.name, size_bytes: f.size, content_type: f.type || "application/octet-stream" }));
  const next = [...current, ...added.filter((a) => !current.some((c) => c.name === a.name))];
  if (next.length > MAX_ATTACHMENTS) toast.error(`Можно прикрепить не больше ${MAX_ATTACHMENTS} файлов`);
  return next.slice(0, MAX_ATTACHMENTS);
}
