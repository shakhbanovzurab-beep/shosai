"use client";

import { useTranslations } from "use-intl";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

import type { ContextRoles } from "../domain/contract";
import { ContextRoleSwitches } from "./context-role-switches";
import { OwnStep, PlacedStep } from "./preview-steps";

type PreviewProps = { content: string; roles: ContextRoles };

/** Куда подмешивается контекст и что получает модель: человек видит свой текст на его месте, пока пишет. */
export function SystemMessagePreview({ content, roles }: PreviewProps) {
  const t = useTranslations("studio");
  // Studio хранит текст без пробелов по краям — так он и уходит модели.
  const sent = content.trim();
  const nowhere = roles !== "all" && roles.length === 0;

  return (
    <Card className="h-fit shadow-xs">
      <CardHeader>
        <CardTitle>{t("preview.title")}</CardTitle>
        <CardDescription>{t("preview.description")}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <ContextRoleSwitches roles={roles} />
        <Separator />
        <ol className="flex flex-col gap-2">
          <PlacedStep number={1} title={t("preview.platform")} hint={t("preview.platformHint")} />
          <OwnStep
            number={2}
            title={t("context.title")}
            hint={nowhere ? t("preview.contextNowhere") : t("preview.contextHint")}
          >
            {sent ? (
              <p dir="auto" className="line-clamp-6 whitespace-pre-wrap break-words text-sm leading-5">
                {sent}
              </p>
            ) : (
              <p className="text-muted-foreground text-sm">{t("preview.empty")}</p>
            )}
          </OwnStep>
          <PlacedStep number={3} title={t("preview.rolePrompt")} hint={t("preview.rolePromptHint")} />
          <PlacedStep number={4} title={t("preview.question")} hint={t("preview.questionHint")} />
        </ol>
      </CardContent>
    </Card>
  );
}
