import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import { ConnectorConsentDemo } from "@/features/settings/mocks/connector-consent-demo";
import { useSearchParams } from "@/lib/navigation";

/**
 * Обратный адрес моков для решения: установка Slack для командных чатов (`flow=chats`, мок маршрута
 * `/v1/integrations/oauth/slack/callback`). Коннекторы настроек идут на бэкенд, к провайдеру.
 */
function callbackFor(connector: string, state: string) {
  return (decision: "allow" | "deny") => {
    const query = new URLSearchParams({ state, decision });
    return `/v1/integrations/oauth/${encodeURIComponent(connector)}/callback?${query}`;
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
        app={connector === "slack" ? "Slack" : null}
        callback={callbackFor(connector, params.get("state") ?? "")}
      />
    </>
  );
}
