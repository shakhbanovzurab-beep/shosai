import { LEO_MAX_ATTACHMENT_BYTES, LEO_MAX_ATTACHMENTS } from "../domain/attachments";
import { type LeoRequest, leoRequestSchema } from "../domain/request";

/* Parses a request to /api/leo: a JSON `payload` field plus up to LEO_MAX_ATTACHMENTS `files`. */

export async function parseRequest(request: Request): Promise<LeoRequest | null> {
  const formData = await request.formData().catch(() => null);
  const payload = formData?.get("payload");
  if (!formData || typeof payload !== "string") return null;

  const parsed = leoRequestSchema.safeParse(JSON.parse(payload));
  if (!parsed.success) return null;

  const files = formData.getAll("files").filter((entry): entry is File => entry instanceof File);
  if (files.length > LEO_MAX_ATTACHMENTS || files.some((file) => file.size > LEO_MAX_ATTACHMENT_BYTES)) return null;

  return { ...parsed.data, files };
}
