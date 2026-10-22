"use client";

import type { ReactNode } from "react";

import { X } from "lucide-react";
import { toast } from "sonner";
import { useTranslations } from "use-intl";

import { MessengerMark } from "@/components/brand/messenger-mark";
import { Button } from "@/components/ui/button";
import type { MessengerLinksResponse } from "@/features/identity/domain/messenger-links-contract";
import {
  useDismissLinkHint,
  useMessengerLinkActions,
  useMessengerLinks,
} from "@/features/identity/model/messenger-links";
import { useOpenSettings } from "@/features/settings/model/dialog-store";
import { useWorkspace } from "@/features/workspace/model/use-workspace";
import { apiErrorDescription } from "@/lib/api/error-description";

import { type LinkHint, linkHintFor, mayHint } from "../../model/link-hint";
import { useChatSettings, useConnections, useInstallations } from "../../model/resources";

/*
 * Тихая строка на главной пространства для того, кто ещё не может просить Leo из командного чата (CF-D9).
 * Закрытие сохраняется на аккаунте: подсказка не возвращается ни в другом пространстве, ни на другом устройстве.
 * Чаты пространства грузятся, только если подсказка вообще может понадобиться.
 */

function HintLine({ hint, action, children }: { hint: LinkHint; action: ReactNode; children: ReactNode }) {
  const t = useTranslations("chats");
  const common = useTranslations("common");
  const dismiss = useDismissLinkHint();
  return (
    <section
      aria-label={t("hint.label")}
      className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-xl border bg-muted/40 px-4 py-2.5 text-sm"
    >
      <MessengerMark messenger={hint.kind} className="shrink-0 text-muted-foreground" />
      <p className="min-w-0 flex-1 basis-64">{children}</p>
      <div className="flex items-center gap-1">
        {action}
        <Button variant="ghost" size="icon-sm" aria-label={common("actions.close")} onClick={dismiss}>
          <X />
        </Button>
      </div>
    </section>
  );
}

function SlackHint({ hint }: { hint: Extract<LinkHint, { kind: "slack" }> }) {
  const t = useTranslations("chats");
  const { confirm } = useMessengerLinkActions();
  const { account, space } = hint.link;
  const confirmLink = () =>
    confirm.mutate(hint.link.id, {
      onSuccess: () => toast.success(t("hint.slackConfirmed")),
      onError: (error) => toast.error(t("hint.slackFailed"), { description: apiErrorDescription(error) }),
    });
  return (
    <HintLine
      hint={hint}
      action={
        <Button size="sm" variant="outline" disabled={confirm.isPending} onClick={confirmLink}>
          {t("hint.confirm")}
        </Button>
      }
    >
      {t.rich("hint.slack", {
        account: () => <bdi>{account.handle ?? account.name}</bdi>,
        space: () => <bdi>{space?.name}</bdi>,
        chat: () => <bdi>#{hint.chat}</bdi>,
      })}
    </HintLine>
  );
}

function TelegramHint({ hint, bot }: { hint: Extract<LinkHint, { kind: "telegram" }>; bot: string | null }) {
  const t = useTranslations("chats");
  const openSettings = useOpenSettings();
  return (
    <HintLine
      hint={hint}
      action={
        <Button size="sm" variant="outline" onClick={() => openSettings("account", "messengers")}>
          {t("hint.linkTelegram")}
        </Button>
      }
    >
      {t.rich(bot ? "hint.telegram" : "hint.telegramShort", {
        chat: () => <bdi>{hint.chat}</bdi>,
        ask: () => (
          <span className="font-medium">{t.rich("hint.ask", { bot: () => <bdi dir="ltr">@{bot}</bdi> })}</span>
        ),
      })}
    </HintLine>
  );
}

function WorkspaceHint({ links }: { links: MessengerLinksResponse }) {
  const { ws } = useWorkspace();
  const connections = useConnections(ws);
  const installations = useInstallations(ws);
  const settings = useChatSettings(ws);
  if (connections.status !== "ready" || installations.status !== "ready") return null;
  const hint = linkHintFor(links, connections.data.items, installations.data.items);
  if (hint?.kind === "slack") return <SlackHint hint={hint} />;
  // Пример с ником бота появляется вместе со строкой, а не после неё: без сдвига вёрстки.
  if (hint?.kind !== "telegram" || settings.status === "loading") return null;
  const served = settings.status === "ready" ? settings.data.messengers : [];
  const telegram = served.find((messenger) => messenger.messenger === "telegram");
  return <TelegramHint hint={hint} bot={telegram?.messenger === "telegram" ? telegram.bot_username : null} />;
}

export function MessengerLinkHint() {
  const links = useMessengerLinks();
  return links.isSuccess && mayHint(links.data) ? <WorkspaceHint links={links.data} /> : null;
}
