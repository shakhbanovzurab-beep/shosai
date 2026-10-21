import { siJira } from "simple-icons";
import { useTranslations } from "use-intl";

import { SimpleIcon } from "@/components/simple-icon";

import type { JiraIssueRef } from "../domain/tasks-contract";

/** The Jira issue key, e.g. "WEB-142", linking to the issue in Jira. */
export function JiraKey({ issue }: { issue: JiraIssueRef }) {
  const t = useTranslations("kanban");
  return (
    <a
      href={issue.url}
      target="_blank"
      rel="noopener noreferrer"
      onPointerDown={(event) => event.stopPropagation()}
      className="relative z-10 inline-flex w-fit items-center gap-1 rounded font-mono text-muted-foreground text-xs hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
    >
      <SimpleIcon icon={siJira} aria-hidden="true" className="size-3 fill-current" />
      {issue.key}
      <span className="sr-only">{t("card.jiraIssue", { type: issue.type })}</span>
    </a>
  );
}
