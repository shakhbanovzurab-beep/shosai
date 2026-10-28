import type { Connector, ConnectorCredentials } from "./connectors-contract";

/* Что человек вводит, чтобы подключить приложение секретом (план connectors §3.7). */

// Адрес сервера нужен только CalDAV: у остальных приложений он известен заранее.
const NEEDS_ADDRESS: ReadonlySet<string> = new Set(["caldav"]);

export const needsAddress = (connector: Pick<Connector, "id">) => NEEDS_ADDRESS.has(connector.id);

/** Тело `POST /v1/connectors/{app}/credentials` из полей формы: ровно один секрет, пустое поле — null. */
export function credentialsFrom(
  connector: Pick<Connector, "id" | "auth">,
  field: (name: string) => string,
): ConnectorCredentials {
  const value = (name: string) => field(name).trim() || null;
  if (connector.auth === "api_key") return { api_key: value("api_key") };
  if (connector.auth === "webhook") return { webhook_url: value("webhook_url") };
  return {
    login: value("login"),
    password: value("password"),
    address: needsAddress(connector) ? value("address") : null,
  };
}
