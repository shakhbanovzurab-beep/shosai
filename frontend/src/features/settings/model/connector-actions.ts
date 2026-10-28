"use client";

import type { ReactNode } from "react";

import { toast } from "sonner";

import { apiErrorDescription } from "@/lib/api/error-description";
import { ApiError } from "@/lib/api/errors";

import { connectorsApi } from "../api/connectors-api";
import {
  type Connector,
  type ConnectorCredentials,
  connectorRefusalOf,
  flowErrorOf,
} from "../domain/connectors-contract";
import { connectorsResource } from "./settings-resources";
import type { ConnectorWords } from "./words";

/** Отказ словами кабинета, если код ему знаком; иначе текст сервера и id запроса для поддержки. */
export function describeConnectorFailure(error: unknown, t: ConnectorWords): ReactNode {
  const code = error instanceof ApiError ? connectorRefusalOf(error.code) : null;
  return code === null ? apiErrorDescription(error) : t(`refusals.${code}`);
}

/** Почему поток OAuth не подключил приложение — по коду со страницы возврата. */
export function describeFlowError(code: string | null, t: ConnectorWords): string {
  const known = flowErrorOf(code);
  return known === null ? t("callback.error.body") : t(`flowErrors.${known}`);
}

const replace = (connector: Connector) =>
  connectorsResource.update((data) => ({
    items: data.items.map((item) => (item.id === connector.id ? connector : item)),
  }));

/** Отключает приложение: строка сразу пустеет, список перечитывается — приложение могли перестать предлагать. */
export async function disconnectConnector(connector: Connector, t: ConnectorWords) {
  replace({
    ...connector,
    connected: false,
    account: null,
    status: "not_connected",
    problem: null,
    connection_id: null,
    connected_at: null,
  });
  try {
    await connectorsApi.disconnect(connector.id);
    toast.success(t("toasts.disconnected", { name: connector.name }));
  } catch (error) {
    replace(connector);
    toast.error(t("toasts.disconnectFailed", { name: connector.name }), {
      description: describeConnectorFailure(error, t),
    });
    return;
  }
  void connectorsResource.refresh();
}

/** Подключает приложение по секрету; ошибка — для формы, null — подключено. */
export async function connectWithCredentials(
  connector: Connector,
  credentials: ConnectorCredentials,
  t: ConnectorWords,
): Promise<ReactNode | null> {
  try {
    replace(await connectorsApi.connectWithCredentials(connector.id, credentials));
    toast.success(t("toasts.connected", { name: connector.name }));
    return null;
  } catch (error) {
    return describeConnectorFailure(error, t);
  }
}
