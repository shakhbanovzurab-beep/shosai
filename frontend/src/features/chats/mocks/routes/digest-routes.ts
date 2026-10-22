import { digestOf } from "../store/digests";
import { answer, type Ctx, inWorkspace } from "./http";

/*
 * Дайджест чата (chats §1.2–§1.3). «Сделать задачей» (`…/task-proposals`) отвечают моки leo: карточку
 * одобрения создаёт агент, а слайс chats от leo не зависит.
 */

const same = <T>(value: T) => value;

/** /v1/workspaces/[id]/chats/[chatId]/digests/[digestId] */
export const digestRoute = {
  async GET(_request: Request, { params }: Ctx<"id" | "chatId" | "digestId">) {
    const { chatId, digestId } = await params;
    return inWorkspace(params, "member", (ws) => answer(digestOf(ws, chatId, digestId), same));
  },
};
