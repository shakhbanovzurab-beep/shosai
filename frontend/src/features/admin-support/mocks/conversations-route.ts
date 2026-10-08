import { detail, JsonResponse } from "@/mocks/runtime";

import type { ConversationDetail, ConversationsResponse } from "../domain/contract";
import { conversationsQuerySchema, sendMessageSchema, updateConversationSchema } from "../domain/schemas";
import { addMessage, getConversation, listConversations, updateConversation } from "./support-demo";

type Context = { params: Promise<{ id: string }> };

/** `/api/admin/support/conversations`: the inbox for one status tab, optionally only mine. */
export const conversationsRoute = {
  async GET(request: Request) {
    const { searchParams } = new URL(request.url);
    const query = conversationsQuerySchema.safeParse({
      status: searchParams.get("status"),
      mine: searchParams.get("mine"),
    });
    if (!query.success) return detail("Неверные параметры фильтра.", 422);
    return JsonResponse.json<ConversationsResponse>(listConversations(query.data.status, query.data.mine));
  },
};

/** `/api/admin/support/conversations/{id}`: one conversation, and changing its status, assignee or priority. */
export const conversationRoute = {
  async GET(_request: Request, { params }: Context) {
    const { id } = await params;
    const conversation = getConversation(id);
    return conversation ? JsonResponse.json<ConversationDetail>(conversation) : detail("Разговор не найден.", 404);
  },

  async PATCH(request: Request, { params }: Context) {
    const { id } = await params;
    const body = updateConversationSchema.safeParse(await request.json().catch(() => null));
    if (!body.success) return detail(body.error.issues[0]?.message ?? "Неверный запрос.", 422);
    const result = updateConversation(id, body.data);
    return result.ok ? JsonResponse.json<ConversationDetail>(result.detail) : detail(result.message, result.status);
  },
};

/** `/api/admin/support/conversations/{id}/messages`: a reply or an internal note. */
export const conversationMessagesRoute = {
  async POST(request: Request, { params }: Context) {
    const { id } = await params;
    const body = sendMessageSchema.safeParse(await request.json().catch(() => null));
    if (!body.success) return detail(body.error.issues[0]?.message ?? "Неверное сообщение.", 422);
    const conversation = addMessage(id, body.data.body, body.data.kind, body.data.attachments);
    return conversation
      ? JsonResponse.json<ConversationDetail>(conversation, { status: 201 })
      : detail("Разговор не найден.", 404);
  },
};
