import { apiRequest, jsonBody } from "@/lib/api-client";

import type {
  CannedRepliesResponse,
  ConversationDetail,
  ConversationsResponse,
  SendMessageRequest,
  StatusFilter,
  UpdateConversationRequest,
} from "../domain/contract";

const request = <T>(path: string, init?: RequestInit) => apiRequest<T>(`/api/admin/support${path}`, init);
const conversationPath = (id: string) => `/conversations/${encodeURIComponent(id)}`;

export const supportApi = {
  list: (status: StatusFilter, mine: boolean) =>
    request<ConversationsResponse>(`/conversations?${new URLSearchParams({ status, mine: String(mine) })}`),
  get: (id: string) => request<ConversationDetail>(conversationPath(id)),
  send: (id: string, message: SendMessageRequest) =>
    request<ConversationDetail>(`${conversationPath(id)}/messages`, jsonBody("POST", message)),
  update: (id: string, patch: UpdateConversationRequest) =>
    request<ConversationDetail>(conversationPath(id), jsonBody("PATCH", patch)),
  cannedReplies: () => request<CannedRepliesResponse>("/canned-replies"),
};
