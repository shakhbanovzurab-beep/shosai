import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import { ConnectorConsentDemo } from "@/features/settings/mocks/connector-consent-demo";
import { useSearchParams } from "@/lib/navigation";

/**
 * Обратный адрес бэкенда для решения: коннекторы настроек или установка Slack для командных чатов
 * (`flow=chats`, маршрут connectors `/v1/integrations/oauth/slack/callback`).
 */
function callbackFor(flow: string | null, connector: string, state: string) {
  return (decision: "allow" | "deny") => {
    const query = new URLSearchParams({ state, decision });
    if (flow === "chats") return `/v1/integrations/oauth/${encodeURIComponent(connector)}/callback?${query}`;
    return `/api/settings/connectors/${encodeURIComponent(connector)}/callback?${query}`;
  };
}

/** Заглушка экрана согласия OAuth провайдера, только в разработке. */
export function Component() {
  const t = useTranslations("settingsConnectors");
  const params = useSearchParams();
  const connector = params.get("connector") ?? "";
  return (
    <>
      <PageMeta title={t("consent.metaTitle")} />
      <ConnectorConsentDemo
        connector={connector}
        callback={callbackFor(params.get("flow"), connector, params.get("state") ?? "")}
      />
    </>
  );
}
