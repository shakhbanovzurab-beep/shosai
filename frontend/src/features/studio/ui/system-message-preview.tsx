import { useFormatter, useTranslations } from "use-intl";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type StepProps = { number: number; title: string; hint: string; children?: React.ReactNode };

/** Номер, название и откуда берётся часть; номер для глаз, порядок читателю даёт сам список. */
function StepHeading({ number, title, hint }: Omit<StepProps, "children">) {
  const format = useFormatter();
  return (
    <div className="flex items-start gap-3">
      <span
        aria-hidden="true"
        className="flex size-5 shrink-0 items-center justify-center rounded-full bg-background font-medium text-muted-foreground text-xs tabular-nums ring-1 ring-border"
      >
        {format.number(number)}
      </span>
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="font-medium text-sm leading-5">{title}</span>
        <span className="text-muted-foreground text-xs">{hint}</span>
      </div>
    </div>
  );
}

/** Часть, которую добавляет Shosai: человек видит только её место в порядке. */
function PlacedStep(props: StepProps) {
  return (
    <li className="rounded-lg bg-muted/40 p-3">
      <StepHeading {...props} />
    </li>
  );
}

/** Часть человека: его текст в том виде, в каком он уйдёт модели. */
function OwnStep({ children, ...heading }: StepProps) {
  return (
    <li className="rounded-lg border-primary border-s-2 bg-muted/40 p-3">
      <StepHeading {...heading} />
      <div className="mt-2 ps-8">{children}</div>
    </li>
  );
}

/** Что получает модель и в каком порядке: человек видит свой текст на его месте, пока пишет. */
export function SystemMessagePreview({ content }: { content: string }) {
  const t = useTranslations("studio");
  // Studio хранит текст без пробелов по краям — так он и уходит модели.
  const sent = content.trim();

  return (
    <Card className="h-fit shadow-xs">
      <CardHeader>
        <CardTitle>{t("preview.title")}</CardTitle>
        <CardDescription>{t("preview.description")}</CardDescription>
      </CardHeader>
      <CardContent>
        <ol className="flex flex-col gap-2">
          <PlacedStep number={1} title={t("preview.platform")} hint={t("preview.platformHint")} />
          <OwnStep number={2} title={t("context.title")} hint={t("preview.contextHint")}>
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
