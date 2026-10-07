import { z } from "zod";

import { LANGUAGE_CODES, type LanguageCode } from "@/lib/language";

import { LEO_MAX_ATTACHMENTS } from "./attachments";

/* The JSON `payload` of a request to /api/leo; the files travel next to it and are checked on the server. */

const attachmentSchema = z.object({
  name: z.string().max(255),
  size: z.number().int().nonnegative(),
  type: z.string().max(255),
});

export const leoRequestSchema = z.object({
  messages: z
    .array(
      z
        .object({
          role: z.enum(["user", "assistant"]),
          content: z.string().trim().max(4000),
          attachments: z.array(attachmentSchema).max(LEO_MAX_ATTACHMENTS).optional(),
        })
        .refine((m) => m.content.length > 0 || (m.attachments?.length ?? 0) > 0, "Message is empty"),
    )
    .min(1)
    .max(50),
  page: z.string().max(200).optional(),
  /** The interface language; the server combines it with Settings › Leo › Response language. */
  locale: z.enum(LANGUAGE_CODES).optional(),
  /** Where the user asked: Personal, or a workspace (whose knowledge the server filters by permission). */
  context: z
    .discriminatedUnion("kind", [
      z.object({ kind: z.literal("personal") }),
      z.object({ kind: z.literal("workspace"), workspace_id: z.string().min(1).max(64) }),
      z.object({ kind: z.literal("hub"), hub_id: z.string().min(1).max(64) }),
    ])
    .optional(),
});

export type LeoRequest = z.infer<typeof leoRequestSchema> & { files: File[] };

/** A request as the agent runs it: everything it must write, it writes in `answerLanguage`. */
export type LeoTurn = LeoRequest & { answerLanguage: LanguageCode };
