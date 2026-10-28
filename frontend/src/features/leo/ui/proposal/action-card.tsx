"use client";

import type { KeyboardEvent, ReactNode } from "react";

import { cn } from "cn";
import { Clock, FileText, Globe, ListTodo, Mail, MessageSquare, ShieldAlert, Sparkles } from "lucide-react";
import { useFormatter, useNow, useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";

import { taintOf } from "../../domain/card-labels";
import { type LeoProposal, proposalCardId } from "../../domain/proposals";

/*
 * Карточка предложенного действия (Leo §13.3: ActionCard Root/Header/Preview/Actions). Превью считает сервер;
 * ⌘/Ctrl+Enter одобряет, Esc отклоняет, пока фокус в карточке. После решения карточка сворачивается в строку.
 */

/** Значок по семейству инструмента (`mail.send` → письмо); незнакомое семейство — общий значок. */
function ToolIcon({ tool }: { tool: string }) {
  const family = tool.slice(0, tool.indexOf(".") + 1);
  if (family === "mail.") return <Mail className="size-4" />;
  if (family === "notes.") return <FileText className="size-4" />;
  if (family === "slack.") return <MessageSquare className="size-4" />;
  if (family === "tasks.") return <ListTodo className="size-4" />;
  if (family === "web.") return <Globe className="size-4" />;
  return <Sparkles className="size-4" />;
}

export function ActionCardRoot({
  proposal,
  onApprove,
  onReject,
  children,
}: {
  proposal: LeoProposal;
  onApprove: () => void;
  onReject: () => void;
  children: ReactNode;
}) {
  const keys = (event: KeyboardEvent) => {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      onApprove();
    }
    if (event.key === "Escape") {
      // Esc отклоняет карточку, а не закрывает панель Leo вокруг неё.
      event.stopPropagation();
      onReject();
    }
  };
  return (
    <Card
      id={proposalCardId(proposal.id)}
      tabIndex={-1}
      size="sm"
      role="group"
      aria-label={proposal.title}
      onKeyDown={keys}
      className={cn(
        "scroll-my-4 outline-none focus-visible:ring-2 focus-visible:ring-ring",
        proposal.warning && "ring-amber-500/50",
      )}
    >
      {children}
    </Card>
  );
}

export function ActionCardHeader({ proposal }: { proposal: LeoProposal }) {
  const t = useTranslations("leoCards");
  const { kind, app } = proposal.origin;
  const origin = kind === "mcp" ? t("card.origin.mcp", { app: app ?? "MCP" }) : t(`card.origin.${kind}`);
  return (
    <CardHeader className="flex items-start gap-3">
      <span className="grid size-8 shrink-0 place-items-center rounded-lg border bg-muted/40" aria-hidden="true">
        <ToolIcon tool={proposal.tool} />
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <CardTitle dir="auto">{proposal.title}</CardTitle>
        <CardDescription>
          {t("card.space", { space: proposal.space })} · {origin}
        </CardDescription>
        {proposal.reversibility === "irreversible" || proposal.warning ? (
          <div className="flex flex-wrap gap-1.5">
            {proposal.reversibility === "irreversible" ? (
              <Badge variant="outline">{t("card.irreversible")}</Badge>
            ) : null}
            {proposal.warning ? <Badge variant="destructive">{t("card.warning")}</Badge> : null}
          </div>
        ) : null}
      </div>
    </CardHeader>
  );
}

/** Прочитанное прогоном было похоже на указания для Leo (decisions' `content.injection`): смотреть вдвойне. */
export function ActionCardSuspicion() {
  const t = useTranslations("leoCards");
  return (
    <CardContent>
      <p role="note" className="flex items-start gap-2 font-medium text-destructive text-xs">
        <ShieldAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
        <span dir="auto">{t("card.suspicious")}</span>
      </p>
    </CardContent>
  );
}

/** Действие готовилось после внешнего текста — человек видит, после какого. */
export function ActionCardTaint({ label }: { label: string | null }) {
  const t = useTranslations("leoCards");
  if (!label) return null;
  const { key, server } = taintOf(label);
  return (
    <CardContent>
      <p className="flex items-start gap-2 text-muted-foreground text-xs">
        <ShieldAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
        <span dir="auto">
          {key === "mcp" ? t("card.taint.mcp", { server: server ?? "MCP" }) : t(`card.taint.${key}`)}
        </span>
      </p>
    </CardContent>
  );
}

function Expires({ at }: { at: string }) {
  const t = useTranslations("leoCards");
  const format = useFormatter();
  const now = useNow({ updateInterval: 60_000 });
  return (
    <span className="me-auto flex items-center gap-1.5 text-muted-foreground text-xs">
      <Clock className="size-3.5" aria-hidden="true" />
      {t("card.expires", { time: format.relativeTime(new Date(at), now) })}
    </span>
  );
}

export function ActionCardActions({
  proposal,
  busy,
  approveLabel,
  approveDisabled,
  onApprove,
  onReject,
}: {
  proposal: LeoProposal;
  busy: boolean;
  approveLabel: string;
  /** Одобрять нечего: например, ни одна правка не выбрана. Отклонить при этом можно. */
  approveDisabled: boolean;
  onApprove: () => void;
  onReject: () => void;
}) {
  const t = useTranslations("leoCards");
  return (
    <CardFooter className="flex flex-wrap items-center gap-2">
      <Expires at={proposal.expires_at} />
      {/* Кнопки переносятся вместе: в узкой панели Leo решение не разрывается на две строки. */}
      <div className="ms-auto flex items-center gap-2">
        <Button variant="ghost" size="sm" disabled={busy} aria-keyshortcuts="Escape" onClick={onReject}>
          {t("card.decline")}
        </Button>
        <Button
          size="sm"
          disabled={busy || approveDisabled}
          aria-keyshortcuts="Meta+Enter Control+Enter"
          onClick={onApprove}
        >
          {busy ? <Spinner data-icon="inline-start" /> : null}
          {approveLabel}
        </Button>
      </div>
    </CardFooter>
  );
}
