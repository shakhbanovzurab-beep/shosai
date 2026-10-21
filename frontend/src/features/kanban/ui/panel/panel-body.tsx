"use client";

import { ExternalLink } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";

import type { TaskDetail } from "../../domain/tasks-contract";
import { useBoardSelector } from "../../model/board-hooks";
import { useEditable } from "../board-store";
import { PanelDescription, ReadOnlyDescription } from "./panel-description";
import { JiraFields, PanelFields } from "./panel-fields";
import { PanelHeader } from "./panel-header";
import { PanelSource } from "./panel-source";

/** Задача в приложении: заголовок, поля, описание, откуда она. Подзадачи, вложения и комментарии — шаг 6. */
function AppTask({ detail, editable }: { detail: TaskDetail; editable: boolean }) {
  return (
    <div className="flex flex-col gap-6">
      <PanelHeader detail={detail} editable={editable} />
      <PanelFields detail={detail} editable={editable} />
      <PanelDescription key={detail.id} taskId={detail.id} markdown={detail.description} />
      <PanelSource source={detail.source} />
    </div>
  );
}

/** Задача Jira: только поля Jira; остальное живёт в Jira (KG-D8). */
function JiraTask({ detail, editable }: { detail: TaskDetail; editable: boolean }) {
  const t = useTranslations("kanbanPanel");
  const jira = detail.jira;
  return (
    <div className="flex flex-col gap-6">
      <PanelHeader detail={detail} editable={editable} />
      <JiraFields detail={detail} editable={editable} />
      <ReadOnlyDescription text={detail.description} />
      {jira ? (
        <div className="flex flex-col items-start gap-2">
          <Button asChild variant="outline" size="sm">
            <a href={jira.url} target="_blank" rel="noopener noreferrer">
              <ExternalLink data-icon="inline-start" className="rtl:-scale-x-100" />
              {t("jira.open", { key: jira.key })}
            </a>
          </Button>
          <p className="text-muted-foreground text-sm">{t("jira.elsewhere")}</p>
        </div>
      ) : null}
    </div>
  );
}

/** Тело панели: на доске Jira пока идёт первая синхронизация или она остановлена — только чтение. */
export function PanelBody({ detail }: { detail: TaskDetail }) {
  const boardEditable = useEditable();
  const onThisBoard = useBoardSelector((s) => s.cards[detail.id] !== undefined);
  const editable = onThisBoard ? boardEditable : true;
  return detail.jira ? (
    <JiraTask detail={detail} editable={editable} />
  ) : (
    <AppTask detail={detail} editable={editable} />
  );
}
