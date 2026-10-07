import type { IssueDetail } from "./contract";
import { formatFullDateTime } from "./format";
import { SEVERITY_LABEL, SOURCE_LABEL, STATUS_LABEL } from "./labels";

const fence = "```";

/** A Markdown summary to paste into a task tracker or a chat with a developer. */
export function developerSummary(issue: IssueDetail, pageUrl: string) {
  const source = issue.platform_component
    ? `${SOURCE_LABEL[issue.source]} (${issue.platform_component})`
    : SOURCE_LABEL[issue.source];
  const frames = issue.stack
    .slice(0, 15)
    .map((frame) => `${frame.in_app ? "→" : " "} ${frame.function}  ${frame.file}${frame.line ? `:${frame.line}` : ""}`)
    .join("\n");
  const crumbs = issue.breadcrumbs
    .slice(-10)
    .map((crumb) => `- \`${crumb.timestamp}\` [${crumb.category}] ${crumb.message}`)
    .join("\n");

  return [
    `## ${issue.title}`,
    "",
    `- **ID:** ${issue.id} · **Fingerprint:** \`${issue.fingerprint}\``,
    `- **Источник:** ${source}`,
    `- **Уровень:** ${SEVERITY_LABEL[issue.severity]} · **Статус:** ${STATUS_LABEL[issue.status]}`,
    `- **Где:** \`${issue.culprit}\``,
    `- **Версия:** ${issue.latest_version} · **ОС:** ${issue.context.os_version} · **Устройство:** ${issue.context.device}`,
    `- **События:** ${issue.event_count} · **Пользователи:** ${issue.user_count}`,
    `- **Впервые:** ${formatFullDateTime(issue.first_seen)} · **Последняя:** ${formatFullDateTime(issue.last_seen)}`,
    issue.support_ticket
      ? `- **Обращение в поддержку:** #${issue.support_ticket.number} ${issue.support_ticket.subject}`
      : null,
    `- **Ссылка:** ${pageUrl}`,
    "",
    "### Стек вызовов",
    "",
    fence,
    `${issue.exception_type}: ${issue.message}`,
    frames,
    fence,
    crumbs ? "\n### Хлебные крошки\n" : null,
    crumbs || null,
  ]
    .filter((line) => line !== null)
    .join("\n");
}
