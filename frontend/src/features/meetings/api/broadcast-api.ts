import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

/* Маршруты трансляции (MR-D7, docs/meetings-api.md): ведущего — по входу, ссылки — по пропуску комнаты. */

export type BroadcastOut = components["schemas"]["BroadcastOut"];
export type LiveTicketOut = components["schemas"]["LiveTicketOut"];
export type LiveStateOut = components["schemas"]["LiveStateOut"];
export type LiveChatMessageOut = components["schemas"]["LiveChatMessageOut"];
type LiveChatPageOut = components["schemas"]["LiveChatPageOut"];

const CHAT_PAGE = 200;
const link = (token: string) => ({ token });
const withPass = (token: string, roomPass: string) => ({ path: link(token), header: { "X-Room-Pass": roomPass } });

export const broadcastApi = {
  /** Новая трансляция ведущего; повтор с тем же ключом — та же трансляция. */
  create: (title: string, waitingRoom: boolean, idempotencyKey: string): Promise<BroadcastOut> =>
    dataOf(
      apiClient.POST("/v1/meetings/broadcasts", {
        params: { header: { "Idempotency-Key": idempotencyKey } },
        body: { title, waiting_room: waitingRoom },
      }),
    ),
  start: (id: string): Promise<BroadcastOut> =>
    dataOf(apiClient.POST("/v1/meetings/broadcasts/{broadcast_id}/start", { params: { path: { broadcast_id: id } } })),
  end: (id: string): Promise<BroadcastOut> =>
    dataOf(apiClient.POST("/v1/meetings/broadcasts/{broadcast_id}/end", { params: { path: { broadcast_id: id } } })),
  /** Что ссылка отвечает: гость называет себя, вошедший человек входит под именем профиля. */
  join: (token: string, name: string | null): Promise<LiveTicketOut> =>
    dataOf(
      apiClient.POST("/v1/meetings/live/{token}/join", {
        params: { path: link(token) },
        body: name === null ? {} : { name },
      }),
    ),
  knock: (token: string, knock: string): Promise<LiveTicketOut> =>
    dataOf(apiClient.POST("/v1/meetings/live/{token}/knock", { params: { path: link(token) }, body: { knock } })),
  state: (token: string, roomPass: string): Promise<LiveStateOut> =>
    dataOf(apiClient.GET("/v1/meetings/live/{token}/state", { params: withPass(token, roomPass) })),
  say: (token: string, roomPass: string, text: string, idempotencyKey: string): Promise<LiveChatMessageOut> =>
    dataOf(
      apiClient.POST("/v1/meetings/live/{token}/chat", {
        params: { path: link(token), header: { "X-Room-Pass": roomPass, "Idempotency-Key": idempotencyKey } },
        body: { text },
      }),
    ),
  chatAfter: (token: string, roomPass: string, after: number): Promise<LiveChatPageOut> =>
    dataOf(
      apiClient.GET("/v1/meetings/live/{token}/chat", {
        params: { ...withPass(token, roomPass), query: { after, limit: CHAT_PAGE } },
      }),
    ),
  hand: (token: string, roomPass: string, raised: boolean): Promise<void> =>
    dataOf(apiClient.PUT("/v1/meetings/live/{token}/hand", { params: withPass(token, roomPass), body: { raised } })),
  answerHand: (token: string, roomPass: string, principal: string, invite: boolean): Promise<void> =>
    dataOf(
      apiClient.POST("/v1/meetings/live/{token}/hands/{principal}", {
        params: { path: { token, principal }, header: { "X-Room-Pass": roomPass } },
        body: { invite },
      }),
    ),
  admit: (token: string, roomPass: string, knock: string, admitted: boolean): Promise<void> =>
    dataOf(
      apiClient.POST("/v1/meetings/live/{token}/admissions/{knock_id}", {
        params: { path: { token, knock_id: knock }, header: { "X-Room-Pass": roomPass } },
        body: { admitted },
      }),
    ),
  seat: (
    token: string,
    roomPass: string,
    principal: string,
    change: { on_air?: boolean; role?: "cohost" | "speaker" },
  ): Promise<void> =>
    dataOf(
      apiClient.PATCH("/v1/meetings/live/{token}/members/{principal}", {
        params: { path: { token, principal }, header: { "X-Room-Pass": roomPass } },
        body: change,
      }),
    ),
  unseat: (token: string, roomPass: string, principal: string): Promise<void> =>
    dataOf(
      apiClient.DELETE("/v1/meetings/live/{token}/members/{principal}", {
        params: { path: { token, principal }, header: { "X-Room-Pass": roomPass } },
      }),
    ),
  stepOnStage: (token: string, roomPass: string): Promise<void> =>
    dataOf(apiClient.POST("/v1/meetings/live/{token}/stage", { params: withPass(token, roomPass) })),
};
