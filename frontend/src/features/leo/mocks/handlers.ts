// Моки разработки слайса, по записи на путь. Учебный чат `/api/leo` (NDJSON v1) — для хаба и админки до их шагов
// (agent, 20 и 16): Personal и workspace ходят в `/v1/agent/*`. Предложения Leo — на путях `/v1/agent/actions*`
// (Leo §13.2), пока срез `agent` не опубликует их (шаг 9b, F2-D1).
import { type MockRoute, mockRoute } from "@/mocks/routing";

import { digestTaskProposalsRoute } from "./digest-proposals";
import { leoRoute } from "./leo-route";
import { approveRoute, proposalsRoute, rejectRoute } from "./proposals-route";

export const handlers: MockRoute[] = [
  mockRoute("/api/leo", leoRoute, ["POST"]),
  mockRoute("/v1/agent/actions", proposalsRoute, ["GET"]),
  mockRoute("/v1/agent/actions/:id/approve", approveRoute, ["POST"]),
  mockRoute("/v1/agent/actions/:id/reject", rejectRoute, ["POST"]),
  // «Сделать задачей» из дайджеста чата: путь слайса chats, карточку создаёт агент (CF-D5).
  mockRoute("/v1/workspaces/:id/chats/:chatId/digests/:digestId/task-proposals", digestTaskProposalsRoute, ["POST"]),
];
