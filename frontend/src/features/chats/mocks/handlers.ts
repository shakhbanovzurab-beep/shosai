// Моки разработки слайса chats, по записи на путь: контракт `/v1/workspaces/{id}/chats*` (chats §1.2), пока
// слайс chats не опубликует API (F2-D1). `…/digests/{id}/task-proposals` отвечают моки leo.
import { type MockRoute, mockRoute } from "@/mocks/routing";

import { connectionRoute, connectionsRoute, rejoinRoute, settingsRoute } from "./routes/connections-routes";
import { digestRoute } from "./routes/digest-routes";
import {
  channelsRoute,
  installationRoute,
  installationsRoute,
  slackCallbackRoute,
  slackConnectRoute,
} from "./routes/slack-routes";
import { connectCodeRoute, connectCodesRoute } from "./routes/telegram-routes";

// Статические пути раньше параметрических.
const BASE = "/v1/workspaces/:id/chats";

export const handlers: MockRoute[] = [
  mockRoute(`${BASE}/settings`, settingsRoute, ["GET", "PATCH"]),
  mockRoute(`${BASE}/telegram/connect-codes`, connectCodesRoute, ["POST"]),
  mockRoute(`${BASE}/telegram/connect-codes/:codeId`, connectCodeRoute, ["GET", "DELETE"]),
  mockRoute(`${BASE}/slack/installations`, installationsRoute, ["GET", "POST"]),
  mockRoute(`${BASE}/slack/installations/:installationId`, installationRoute, ["DELETE"]),
  mockRoute(`${BASE}/slack/installations/:installationId/channels`, channelsRoute, ["GET"]),
  mockRoute(`${BASE}/slack`, slackConnectRoute, ["POST"]),
  mockRoute(BASE, connectionsRoute, ["GET"]),
  mockRoute(`${BASE}/:chatId`, connectionRoute, ["GET", "PATCH", "DELETE"]),
  mockRoute(`${BASE}/:chatId/rejoin`, rejoinRoute, ["POST"]),
  mockRoute(`${BASE}/:chatId/digests/:digestId`, digestRoute, ["GET"]),
  mockRoute("/v1/integrations/oauth/slack/callback", slackCallbackRoute, ["GET"]),
];
