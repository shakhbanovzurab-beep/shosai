import { BODY_MAX, MAX_ATTACHMENT_BYTES, MAX_ATTACHMENTS, type TicketAttachment } from "../domain/contract";
import type { Problem } from "./problems";

type ParsedMessage = { form: FormData; body: string; attachments: TicketAttachment[] };

/** Reads `body` and `files` from a multipart message. Returns the parts, or the problem with them. */
export async function parseMessage(request: Request): Promise<{ message: ParsedMessage } | { problem: Problem }> {
  const form = await request.formData().catch(() => null);
  if (!form) return { problem: { code: "notMultipart" } };
  const body = String(form.get("body") ?? "").trim();
  const files = form.getAll("files").filter((part): part is File => part instanceof File && part.size > 0);
  if (!body && files.length === 0) return { problem: { code: "emptyMessage" } };
  if (body.length > BODY_MAX) return { problem: { code: "messageTooLong" } };
  if (files.length > MAX_ATTACHMENTS) return { problem: { code: "tooManyFiles" } };
  const tooBig = files.find((f) => f.size > MAX_ATTACHMENT_BYTES);
  if (tooBig) return { problem: { code: "fileTooBig", name: tooBig.name } };
  // The demo keeps only names and sizes; the backend stores the files and returns their URLs.
  const attachments = files.map((f) => ({ name: f.name, size_bytes: f.size, url: null }));
  return { message: { form, body, attachments } };
}
