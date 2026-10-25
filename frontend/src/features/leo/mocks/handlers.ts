// Моки разработки слайса, по записи на путь. Учебный чат `/api/leo` (NDJSON v1) — для хаба и админки до их шагов
// (agent, 20 и 16): Personal и workspace ходят в `/v1/agent/*`, карточки — в `/v1/agent/actions*` (шаг 10).
import { type MockRoute, mockRoute } from "@/mocks/routing";

import { digestTaskProposalsRoute } from "./digest-proposals";
import { leoRoute } from "./leo-route";

export const handlers: MockRoute[] = [
  mockRoute("/api/leo", leoRoute, ["POST"]),
  // «Сделать задачей» из дайджеста чата: путь слайса chats, карточку создаёт агент (CF-D5).
  mockRoute("/v1/workspaces/:id/chats/:chatId/digests/:digestId/task-proposals", digestTaskProposalsRoute, ["POST"]),
];
