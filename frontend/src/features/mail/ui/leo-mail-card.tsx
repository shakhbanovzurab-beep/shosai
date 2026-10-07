"use client";

import { CircleAlert } from "lucide-react";
import { useTranslations } from "next-intl";
import { ThinkingOrb } from "thinking-orbs";

import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { ResourceState } from "@/lib/polling-resource";

import type { MailInsightsResponse } from "../domain/leo-insights";
import type { LeoMailView } from "../domain/leo-triage";
import type { Mail } from "../domain/mail";
import { insightsResource } from "../model/leo-insights";
import { LeoInsightCard } from "./leo-insight-card";

type LeoMailCardProps = {
  mail: Mail;
  state: ResourceState<MailInsightsResponse>;
  view: LeoMailView | undefined;
};

/** Leo above the open email: its reading once ready, while it reads, or why it couldn't. */
export function LeoMailCard({ mail, state, view }: LeoMailCardProps) {
  const t = useTranslations("mailLeo.card");

  if (state.status === "error") return <ReadError message={state.message} />;
  if (view?.insight.status === "failed") return <ReadError message={t("readFailedHint")} />;
  if (state.status === "loading" || view?.insight.status === "analyzing") return <ReadingCard />;
  // Leo reads the inbox; an email it hasn't seen gets no card.
  return view?.triage ? <LeoInsightCard mail={mail} view={view} /> : null;
}

function ReadError({ message }: { message: string }) {
  const t = useTranslations("mailLeo.card");
  const common = useTranslations("common");

  return (
    <Alert className="shrink-0">
      <CircleAlert />
      <AlertTitle>{t("readFailed")}</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
      <AlertAction>
        <Button variant="outline" size="xs" onClick={() => void insightsResource.refresh()}>
          {common("actions.retry")}
        </Button>
      </AlertAction>
    </Alert>
  );
}

function ReadingCard() {
  const t = useTranslations("mailLeo.card");

  return (
    <Card size="sm" className="shrink-0" role="status">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ThinkingOrb state="searching" size={20} aria-hidden="true" />
          <span className="shimmer font-normal text-muted-foreground">{t("readingEmail")}</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-2" aria-hidden="true">
        <Skeleton className="h-3.5 w-3/4" />
        <Skeleton className="h-3.5 w-full" />
        <Skeleton className="h-3.5 w-1/2" />
      </CardContent>
    </Card>
  );
}
