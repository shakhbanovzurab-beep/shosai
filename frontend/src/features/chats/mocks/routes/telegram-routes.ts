import { cancelCode, createCode, pollCode } from "../store/telegram";
import { answer, answerEmpty, bodyOf, type Ctx, inWorkspace } from "./http";
import { connectCodeSchema } from "./schemas";

/* Коды подключения Telegram (chats §1.2): выдать, опрашивать, отменить. */

const same = <T>(value: T) => value;
const codeOf = async (params: Promise<Record<"id" | "codeId", string>>) => (await params).codeId;

/** /v1/workspaces/[id]/chats/telegram/connect-codes */
export const connectCodesRoute = {
  async POST(request: Request, { params }: Ctx<"id">) {
    return inWorkspace(params, "admin", async (ws) => {
      const body = await bodyOf(request, connectCodeSchema);
      if ("refusal" in body) return body.refusal;
      return answer(createCode(ws, body.data), same, 201);
    });
  },
};

/** /v1/workspaces/[id]/chats/telegram/connect-codes/[codeId] */
export const connectCodeRoute = {
  async GET(_request: Request, { params }: Ctx<"id" | "codeId">) {
    const codeId = await codeOf(params);
    return inWorkspace(params, "admin", (ws) => answer(pollCode(ws, codeId), same));
  },
  async DELETE(_request: Request, { params }: Ctx<"id" | "codeId">) {
    const codeId = await codeOf(params);
    return inWorkspace(params, "admin", (ws) => answerEmpty(cancelCode(ws, codeId)));
  },
};
