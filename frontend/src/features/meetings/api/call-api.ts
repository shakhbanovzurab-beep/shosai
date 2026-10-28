import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

/* Маршруты идущего звонка: чат по пропуску комнаты (MR-D11) и действия владельца по его входу (MR-D2). */

export type ChatMessageOut = components["schemas"]["MeetingChatMessageOut"];
type ChatPage = components["schemas"]["MeetingChatPageOut"];

const room = (roomId: string) => ({ room_id: roomId });
const CHAT_PAGE = 200;

export const callApi = {
  /** Сообщение всем; сервер раздаёт его по каналу данных, отправителю тоже. */
  say: (roomId: string, roomPass: string, text: string, idempotencyKey: string): Promise<ChatMessageOut> =>
    dataOf(
      apiClient.POST("/v1/meetings/rooms/{room_id}/chat", {
        params: { path: room(roomId), header: { "Idempotency-Key": idempotencyKey, "X-Room-Pass": roomPass } },
        body: { text },
      }),
    ),
  /** Сообщения после `after` — догон после переподключения. */
  chatAfter: (roomId: string, roomPass: string, after: number): Promise<ChatPage> =>
    dataOf(
      apiClient.GET("/v1/meetings/rooms/{room_id}/chat", {
        params: { path: room(roomId), header: { "X-Room-Pass": roomPass }, query: { after, limit: CHAT_PAGE } },
      }),
    ),
  remove: (roomId: string, identity: string): Promise<void> =>
    dataOf(
      apiClient.DELETE("/v1/meetings/rooms/{room_id}/participants/{identity}", {
        params: { path: { room_id: roomId, identity } },
      }),
    ),
  lowerHand: (roomId: string, identity: string): Promise<void> =>
    dataOf(
      apiClient.PATCH("/v1/meetings/rooms/{room_id}/participants/{identity}/hand", {
        params: { path: { room_id: roomId, identity } },
        body: { raised: false },
      }),
    ),
  end: (roomId: string): Promise<unknown> =>
    dataOf(apiClient.POST("/v1/meetings/rooms/{room_id}/end", { params: { path: room(roomId) } })),
};
