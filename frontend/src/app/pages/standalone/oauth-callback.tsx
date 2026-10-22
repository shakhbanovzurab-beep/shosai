import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import { ChatsOAuthCallback } from "@/features/chats/ui/oauth/chats-oauth-callback";
import { OAuthCallback } from "@/features/settings/ui/oauth/oauth-callback";
import { useSearchParams } from "@/lib/navigation";

export function Component() {
  const t = useTranslations("settingsConnectors");
  const params = useSearchParams();
  const status = params.get("status");
  const result = status === "connected" || status === "denied" ? status : "error";
  return (
    <>
      <PageMeta title={t("callback.metaTitle")} />
      {params.get("flow") === "chats" ? (
        <ChatsOAuthCallback
          status={result}
          installationId={params.get("installation_id")}
          error={params.get("error")}
        />
      ) : (
        <OAuthCallback connector={params.get("connector") ?? ""} status={result} error={params.get("error")} />
      )}
    </>
  );
}
