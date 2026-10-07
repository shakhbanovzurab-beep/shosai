import { toast } from "sonner";

import { errorMessage } from "@/lib/errors";

import { kbApi } from "../api/kb-api";
import type { ConnectorDefinition } from "../domain/connectors";
import type { Connector } from "../domain/contract";
import { connectorsResource } from "./kb-resources";
import type { SourceWords } from "./words";

/* Connecting, syncing and disconnecting sources. `name` is the source as the user reads it ("Slack", "Website"). */

const replace = (next: Connector) =>
  connectorsResource.update((data) => ({ connectors: data.connectors.map((c) => (c.id === next.id ? next : c)) }));

type ConnectResult = { status: "redirecting" } | { status: "connected" } | { status: "failed"; message: string };

/** Saves a source's settings. OAuth sources hand off to the provider when the backend asks. */
export async function connectSource(
  definition: ConnectorDefinition,
  name: string,
  config: Record<string, string>,
  t: SourceWords,
): Promise<ConnectResult> {
  try {
    const { connector: saved, authorize_url } = await kbApi.connect(definition.id, config);
    if (authorize_url) {
      window.location.assign(authorize_url);
      return { status: "redirecting" };
    }
    replace(saved);
    toast.success(t("toasts.connected", { name }), { description: t("toasts.firstSync") });
    return { status: "connected" };
  } catch (e) {
    return { status: "failed", message: errorMessage(e) ?? t("dialog.connectFailed") };
  }
}

export async function syncSource(definition: ConnectorDefinition, name: string, t: SourceWords) {
  try {
    replace(await kbApi.sync(definition.id));
  } catch (error) {
    toast.error(t("toasts.syncFailed", { name }), { description: errorMessage(error) });
  }
}

export async function disconnectSource(definition: ConnectorDefinition, name: string, t: SourceWords) {
  try {
    await kbApi.disconnect(definition.id);
    toast.success(t("toasts.disconnected", { name }));
  } catch (error) {
    toast.error(t("toasts.disconnectFailed", { name }), { description: errorMessage(error) });
  } finally {
    void connectorsResource.refresh();
  }
}
