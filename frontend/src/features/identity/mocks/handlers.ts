import { type MockRoute, mockRoute } from "@/mocks/routing";

import {
  desktopCodeRoute,
  forgotRoute,
  registerRoute,
  resendRoute,
  resetRoute,
  socialProvidersRoute,
  socialSessionRoute,
  verifyRoute,
} from "./flow-routes";
import { loginRoute, logoutRoute, meRoute, refreshRoute } from "./session-route";

export const handlers: MockRoute[] = [
  mockRoute("/v1/auth/login", loginRoute, ["POST"]),
  mockRoute("/v1/auth/refresh", refreshRoute, ["POST"]),
  mockRoute("/v1/auth/logout", logoutRoute, ["POST"]),
  mockRoute("/v1/auth/register", registerRoute, ["POST"]),
  mockRoute("/v1/auth/register/verify", verifyRoute, ["POST"]),
  mockRoute("/v1/auth/register/resend", resendRoute, ["POST"]),
  mockRoute("/v1/auth/password/forgot", forgotRoute, ["POST"]),
  mockRoute("/v1/auth/password/reset", resetRoute, ["POST"]),
  mockRoute("/v1/auth/social/providers", socialProvidersRoute, ["GET"]),
  mockRoute("/v1/auth/social/complete", socialSessionRoute, ["POST"]),
  mockRoute("/v1/auth/social/register", socialSessionRoute, ["POST"]),
  mockRoute("/v1/auth/desktop/code", desktopCodeRoute, ["POST"]),
  mockRoute("/v1/me", meRoute, ["GET", "PATCH"]),
];
