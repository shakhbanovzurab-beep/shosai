import { type MockRoute, mockRoute } from "@/mocks/routing";

import {
  avatarRoute,
  deletionRoute,
  deviceRoute,
  devicesRoute,
  exportsRoute,
  latestExportRoute,
  otherDevicesRoute,
} from "./account-routes";
import {
  desktopCodeRoute,
  emailResendRoute,
  emailStartRoute,
  emailVerifyRoute,
  resetRoute,
  socialProvidersRoute,
  socialSessionRoute,
} from "./flow-routes";
import {
  confirmLinkRoute,
  hintDismissalRoute,
  linkRequestRoute,
  messengerLinkRoute,
  messengerLinksRoute,
  telegramLinkRoute,
} from "./messenger-links";
import { adminSessionRoute, loginRoute, logoutRoute, meRoute, refreshRoute } from "./session-route";

export const handlers: MockRoute[] = [
  mockRoute("/v1/auth/login", loginRoute, ["POST"]),
  mockRoute("/v1/auth/refresh", refreshRoute, ["POST"]),
  mockRoute("/v1/auth/logout", logoutRoute, ["POST"]),
  mockRoute("/v1/auth/email/start", emailStartRoute, ["POST"]),
  mockRoute("/v1/auth/email/verify", emailVerifyRoute, ["POST"]),
  mockRoute("/v1/auth/email/resend", emailResendRoute, ["POST"]),
  mockRoute("/v1/auth/password/reset", resetRoute, ["POST"]),
  mockRoute("/v1/auth/social/providers", socialProvidersRoute, ["GET"]),
  mockRoute("/v1/auth/social/complete", socialSessionRoute, ["POST"]),
  mockRoute("/v1/auth/social/register", socialSessionRoute, ["POST"]),
  mockRoute("/v1/auth/desktop/code", desktopCodeRoute, ["POST"]),
  mockRoute("/v1/me", meRoute, ["GET", "PATCH"]),
  mockRoute("/v1/me/avatar", avatarRoute, ["PUT", "DELETE"]),
  mockRoute("/v1/me/devices", devicesRoute, ["GET"]),
  mockRoute("/v1/me/devices/sign-out-others", otherDevicesRoute, ["POST"]),
  mockRoute("/v1/me/devices/:device_id", deviceRoute, ["DELETE"]),
  mockRoute("/v1/me/exports", exportsRoute, ["POST"]),
  mockRoute("/v1/me/exports/latest", latestExportRoute, ["GET"]),
  mockRoute("/v1/me/deletion", deletionRoute, ["POST"]),
  mockRoute("/v1/me/messenger-links", messengerLinksRoute, ["GET"]),
  mockRoute("/v1/me/messenger-links/hint-dismissal", hintDismissalRoute, ["POST"]),
  mockRoute("/v1/me/messenger-links/telegram", telegramLinkRoute, ["POST"]),
  mockRoute("/v1/me/messenger-links/telegram/requests/:requestId", linkRequestRoute, ["GET"]),
  mockRoute("/v1/me/messenger-links/:linkId/confirm", confirmLinkRoute, ["POST"]),
  mockRoute("/v1/me/messenger-links/:linkId", messengerLinkRoute, ["DELETE"]),
  mockRoute("/v1/admin/session", adminSessionRoute, ["GET", "POST", "DELETE"]),
];
