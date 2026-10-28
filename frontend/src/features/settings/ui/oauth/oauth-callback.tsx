"use client";

import * as React from "react";

import { CircleCheck, CircleX } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Link } from "@/lib/navigation";

import { OAUTH_MESSAGE_TYPE, type OAuthResultMessage, type OAuthStatus } from "../../domain/connectors-contract";
import { describeFlowError } from "../../model/connector-actions";

interface OAuthCallbackProps {
  readonly connector: string;
  readonly status: OAuthStatus;
  /** Why the flow failed, as the backend's code (`authorization_expired`, `scope_missing`…). */
  readonly error: string | null;
}

export function OAuthCallback({ connector, status, error }: OAuthCallbackProps) {
  const t = useTranslations("settingsConnectors");

  // Report the result to the settings window that opened this popup, then close it.
  React.useEffect(() => {
    const opener = window.opener as Window | null;
    if (!opener || opener.closed) return;
    const message: OAuthResultMessage = { type: OAUTH_MESSAGE_TYPE, connector, status, error };
    opener.postMessage(message, window.location.origin);
    window.close();
  }, [connector, status, error]);

  const Icon = status === "connected" ? CircleCheck : CircleX;

  // Seen only when the page was opened without a popup (or the browser kept it open).
  return (
    <main className="flex min-h-dvh items-center justify-center bg-background p-6">
      <div className="flex max-w-sm flex-col items-center gap-3 text-center">
        <Icon className="size-10 text-muted-foreground" aria-hidden="true" />
        <h1 className="font-medium text-xl">{t(`callback.${status}.title`)}</h1>
        <p className="text-muted-foreground text-sm">
          {status === "error" ? describeFlowError(error, t) : t(`callback.${status}.body`)}
        </p>
        <Button variant="outline" asChild>
          <Link href="/app">{t("callback.back")}</Link>
        </Button>
      </div>
    </main>
  );
}
