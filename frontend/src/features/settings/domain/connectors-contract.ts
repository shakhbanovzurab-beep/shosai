import type { components } from "@/lib/api/generated/schema";

/*
 * Settings › Connectors на `/v1/connectors*` (план connectors §3.7): каталог предложенных приложений и подключения
 * человека. OAuth ведёт бэкенд: `POST /v1/connectors/{app}/authorize` отдаёт страницу согласия провайдера и ставит
 * cookie-привязку браузера; провайдер возвращает на обратный адрес бэкенда, тот — на `/oauth/callback` с `status` и
 * кодом `error`, а страница сообщает итог окну-хозяину. Пароль приложения, ключ или адрес хука уходят в
 * `POST /v1/connectors/{app}/credentials`; `DELETE /v1/connectors/{app}` отключает.
 */

export type Connector = components["schemas"]["ConnectorOut"];
export type ConnectorsResponse = components["schemas"]["ConnectorsOut"];
export type ConnectorCredentials = components["schemas"]["ConnectorCredentialsIn"];
export type ConnectorAuth = Connector["auth"];

export const CONNECTOR_CATEGORIES = ["mail", "calendar", "files", "notes", "communication", "tasks", "crm"] as const;
export type ConnectorCategory = (typeof CONNECTOR_CATEGORIES)[number];

export const isConnectorCategory = (value: string): value is ConnectorCategory =>
  CONNECTOR_CATEGORIES.some((category) => category === value);

/** Почему подключение ждёт человека — каждый код кабинет называет словами. */
export const CONNECTOR_PROBLEMS = [
  "refresh_refused",
  "grant_revoked",
  "scope_missing",
  "admin_consent_required",
  "imap_disabled",
  "provider_subscription_required",
  "credentials_rejected",
] as const;
export type ConnectorProblem = (typeof CONNECTOR_PROBLEMS)[number];

/** Почему поток OAuth кончился ошибкой (`/oauth/callback?status=error&error=<код>`). */
export const FLOW_ERRORS = [
  "authorization_expired",
  "scope_missing",
  "admin_consent_required",
  "provider_unavailable",
  "not_offered",
  "imap_disabled",
  "provider_subscription_required",
] as const;
export type FlowError = (typeof FLOW_ERRORS)[number];

/** Отказы маршрутов коннекторов, которые кабинет называет сам; остальное — текст сервера и id запроса. */
export const CONNECTOR_REFUSALS = [
  "not_offered",
  "not_connected",
  "connect_unavailable",
  "credentials_rejected",
  "rate_limited",
] as const;
export type ConnectorRefusal = (typeof CONNECTOR_REFUSALS)[number];

const known =
  <T extends string>(codes: readonly T[]) =>
  (value: string | null | undefined): T | null =>
    codes.find((code) => code === value) ?? null;

export const connectorProblemOf = known(CONNECTOR_PROBLEMS);
export const flowErrorOf = known(FLOW_ERRORS);
export const connectorRefusalOf = known(CONNECTOR_REFUSALS);

export type OAuthStatus = "connected" | "denied" | "error";

/** Posted by `/oauth/callback` to the window that opened the consent popup; `error` is a flow error's code. */
export type OAuthResultMessage = {
  type: typeof OAUTH_MESSAGE_TYPE;
  connector: string;
  status: OAuthStatus;
  error: string | null;
};

export const OAUTH_MESSAGE_TYPE = "leo:connector-oauth";
