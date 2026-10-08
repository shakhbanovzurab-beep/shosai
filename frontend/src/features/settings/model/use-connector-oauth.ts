"use client";

import * as React from "react";

import { toast } from "sonner";
import { useTranslations } from "use-intl";

import { apiErrorDescription } from "@/lib/api/error-description";

import { settingsApi } from "../api/settings-api";
import { type Connector, OAUTH_MESSAGE_TYPE, type OAuthResultMessage } from "../domain/connectors-contract";
import { connectorsResource } from "./settings-resources";

const POPUP_WIDTH = 520;
const POPUP_HEIGHT = 700;

function openCenteredPopup() {
  const left = Math.round(window.screenX + (window.outerWidth - POPUP_WIDTH) / 2);
  const top = Math.round(window.screenY + (window.outerHeight - POPUP_HEIGHT) / 2);
  return window.open(
    "",
    "leo-connector-oauth",
    `popup,width=${POPUP_WIDTH},height=${POPUP_HEIGHT},left=${left},top=${top}`,
  );
}

function isOAuthMessage(data: unknown): data is OAuthResultMessage {
  return typeof data === "object" && data !== null && (data as { type?: unknown }).type === OAUTH_MESSAGE_TYPE;
}

const replace = (connector: Connector) =>
  connectorsResource.update((data) => ({
    connectors: data.connectors.map((c) => (c.id === connector.id ? connector : c)),
  }));

/**
 * Runs a connector's OAuth 2.0 consent in a popup and reports the outcome. The popup opens right on the
 * click (browsers block popups opened later) and gets the consent URL once the backend returns it.
 */
export function useConnectorOAuth() {
  const t = useTranslations("settingsConnectors");
  const [pendingId, setPendingId] = React.useState<string | null>(null);
  const cleanupRef = React.useRef<(() => void) | null>(null);

  React.useEffect(() => () => cleanupRef.current?.(), []);

  const finish = () => {
    cleanupRef.current?.();
    cleanupRef.current = null;
    setPendingId(null);
  };

  const waitForResult = (connector: Connector, popup: Window) => {
    const onMessage = (event: MessageEvent) => {
      if (event.origin !== window.location.origin || !isOAuthMessage(event.data)) return;
      if (event.data.connector !== connector.id) return;
      finish();
      const name = connector.name;
      if (event.data.status === "connected") toast.success(t("toasts.connected", { name }));
      else if (event.data.status === "denied") toast(t("toasts.notConnected", { name }));
      else toast.error(t("toasts.connectFailed", { name }), { description: event.data.error ?? undefined });
      void connectorsResource.refresh();
    };
    // Closing the popup without finishing counts as a cancel.
    const closedTimer = window.setInterval(() => {
      if (popup.closed) finish();
    }, 500);
    window.addEventListener("message", onMessage);
    cleanupRef.current = () => {
      window.removeEventListener("message", onMessage);
      window.clearInterval(closedTimer);
    };
  };

  const connect = async (connector: Connector) => {
    if (pendingId) return;
    setPendingId(connector.id);
    const popup = openCenteredPopup();
    try {
      const { connector: updated, authorize_url: authorizeUrl } = await settingsApi.setConnected(connector.id, true);
      if (!authorizeUrl) {
        popup?.close();
        replace(updated);
        setPendingId(null);
        return;
      }
      if (!popup) {
        // Popups are blocked: run the consent in this tab; /oauth/callback brings the user back.
        window.location.assign(authorizeUrl);
        return;
      }
      popup.location.href = authorizeUrl;
      popup.focus();
      waitForResult(connector, popup);
    } catch (error) {
      popup?.close();
      setPendingId(null);
      toast.error(t("toasts.connectFailed", { name: connector.name }), { description: apiErrorDescription(error) });
    }
  };

  const disconnect = async (connector: Connector) => {
    replace({ ...connector, connected: false, account: null });
    try {
      replace((await settingsApi.setConnected(connector.id, false)).connector);
      toast.success(t("toasts.disconnected", { name: connector.name }));
    } catch (error) {
      replace(connector);
      toast.error(t("toasts.disconnectFailed", { name: connector.name }), { description: apiErrorDescription(error) });
    }
  };

  return { pendingId, connect, disconnect };
}
