import { ShieldCheck } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";

import { getConnector } from "./demo-connectors";

/**
 * Stand-in for a provider's OAuth consent screen while no backend is configured. It is plainly a demo
 * page in the app's own style and never imitates the provider's sign-in.
 */
export function ConnectorConsentDemo({ connector, state }: { connector: string; state: string }) {
  const t = useTranslations("settingsConnectors");
  const common = useTranslations("common");
  const app = getConnector(connector)?.name;
  const callback = (decision: "allow" | "deny") =>
    `/api/settings/connectors/${encodeURIComponent(connector)}/callback?${new URLSearchParams({ state, decision })}`;

  return (
    <main className="flex min-h-dvh items-center justify-center bg-background p-6">
      <div className="flex w-full max-w-sm flex-col gap-5 rounded-2xl border bg-card p-6">
        <div className="flex flex-col gap-2">
          <span className="w-fit rounded-md bg-muted px-2 py-0.5 font-medium text-muted-foreground text-xs">
            {t("consent.badge")}
          </span>
          <h1 className="font-medium text-xl">{app ? t("consent.title", { app }) : t("consent.titleUnknown")}</h1>
          <p className="text-muted-foreground text-sm">{app ? t("consent.body", { app }) : t("consent.bodyUnknown")}</p>
        </div>
        <p className="flex items-start gap-2 text-muted-foreground text-xs">
          <ShieldCheck className="mt-px size-4 shrink-0" aria-hidden="true" />
          {t("consent.disconnectHint")}
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" asChild>
            <a href={callback("deny")}>{common("actions.cancel")}</a>
          </Button>
          <Button asChild>
            <a href={callback("allow")}>{t("consent.allow")}</a>
          </Button>
        </div>
      </div>
    </main>
  );
}
