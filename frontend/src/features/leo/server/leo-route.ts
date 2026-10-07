import { responseLanguageSetting } from "@/features/settings/server";
import { DEFAULT_LANGUAGE } from "@/lib/language";

import { answerLanguage } from "../domain/answer-language";
import { encodeLeoEvent, type LeoEvent } from "../domain/protocol";
import { runAgent } from "./demo-agent";
import { parseRequest } from "./request";

/** /api/leo: runs the agent and streams its events back as newline-delimited JSON. */
export const leoRoute = {
  async POST(request: Request) {
    const parsed = await parseRequest(request).catch(() => null);

    if (!parsed) {
      return Response.json({ error: "Invalid request" }, { status: 400 });
    }

    const turn = {
      ...parsed,
      answerLanguage: answerLanguage(responseLanguageSetting(), parsed.locale ?? DEFAULT_LANGUAGE),
    };
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      async start(controller) {
        const send = (event: LeoEvent) => {
          // The client may already be gone (Stop button, closed tab); writing then would throw.
          if (!request.signal.aborted) controller.enqueue(encoder.encode(encodeLeoEvent(event)));
        };
        try {
          for await (const event of runAgent(turn, request.signal)) send(event);
        } catch {
          // A code for logs, never shown: the panel words a failed reply itself, in the user's language.
          send({ type: "error", message: "agent_failed" });
        } finally {
          try {
            controller.close();
          } catch {
            // Already closed by the client.
          }
        }
      },
    });

    return new Response(stream, {
      headers: { "Content-Type": "application/x-ndjson; charset=utf-8", "Cache-Control": "no-store" },
    });
  },
};
