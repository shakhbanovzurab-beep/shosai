import { z } from "zod";

import {
  CONVERSATION_STATUSES,
  MAX_ATTACHMENT_BYTES,
  MAX_ATTACHMENTS,
  MESSAGE_MAX,
  PRIORITIES,
  STATUS_FILTERS,
} from "./contract";

/* Request validation of the admin support routes; the demo answers 422 with the first issue's message. */

/** Query of GET /admin/support/conversations; unknown values fall back to the defaults. */
export const conversationsQuerySchema = z.object({
  status: z.enum(STATUS_FILTERS).catch("all"),
  mine: z
    .enum(["true", "false"])
    .catch("false")
    .transform((value) => value === "true"),
});

/** PATCH /admin/support/conversations/{id}: see `UpdateConversationRequest`. */
export const updateConversationSchema = z
  .object({
    status: z.enum(CONVERSATION_STATUSES).optional(),
    assignee: z.string().min(1).nullable().optional(),
    priority: z.enum(PRIORITIES).optional(),
  })
  .refine((p) => p.status !== undefined || p.assignee !== undefined || p.priority !== undefined, {
    error: "Передайте status, assignee или priority.",
  });

/** POST /admin/support/conversations/{id}/messages: see `SendMessageRequest`. */
export const sendMessageSchema = z
  .object({
    body: z.string().trim().max(MESSAGE_MAX, `Не больше ${MESSAGE_MAX} символов.`),
    kind: z.enum(["reply", "note"]),
    attachments: z
      .array(
        z.object({
          name: z.string().min(1).max(255),
          size_bytes: z.number().int().nonnegative().max(MAX_ATTACHMENT_BYTES, "Файл больше 20 МБ."),
          content_type: z.string().max(255),
        }),
      )
      .max(MAX_ATTACHMENTS, `Не больше ${MAX_ATTACHMENTS} файлов.`)
      .default([]),
  })
  .refine((m) => m.body.length > 0 || m.attachments.length > 0, { error: "Сообщение пустое." });
