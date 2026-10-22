"use client";

import { useEffect, useRef } from "react";

import { toast } from "sonner";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { telegramLinkOf, useMessengerLinks } from "@/features/identity/model/messenger-links";
import { useTelegramLink } from "@/features/identity/model/telegram-link";
import { apiErrorDescription } from "@/lib/api/error-description";

import { useSettingsDialog } from "../../../model/dialog-store";
import { SettingsGroup } from "../../settings-row";
import { SlackLinked, SlackProposal } from "./slack-rows";
import { LinkedTelegram, LinkingTelegram } from "./telegram-row";

/*
 * Settings › Account › «Мессенджеры» (chats §1.2, план CHATS-frontend §3.6): привязанный аккаунт мессенджера
 * даёт просить Leo из командного чата с правами человека. У Slack строки нет, пока нет ни предложения, ни
 * привязки: привязать Slack вручную нельзя (CF-D4), а неработающей кнопки здесь не бывает.
 */

/** Отступ группы от верха тела раздела после прокрутки — как его собственный отступ (py-5). */
const ANCHOR_GAP_PX = 20;

export function MessengersGroup() {
  const t = useTranslations("settings");
  const common = useTranslations("common");
  const links = useMessengerLinks();
  const { flow, begin, reset } = useTelegramLink((error) =>
    toast.error(t("messengers.telegram.startFailed"), { description: apiErrorDescription(error) }),
  );
  const items = links.data?.items ?? [];
  const telegram = telegramLinkOf(items);
  const group = useRef<HTMLElement>(null);
  const anchored = useSettingsDialog((state) => state.anchor === "messengers");
  // Открыли из подсказки на главной: группа сразу на виду. Прокручивается только тело раздела —
  // scrollIntoView сдвинул бы и само окно, у которого overflow скрыт.
  useEffect(() => {
    const target = group.current;
    const body = target?.closest<HTMLElement>("[data-settings-scroll]");
    if (!anchored || !target || !body) return;
    body.scrollTop += target.getBoundingClientRect().top - body.getBoundingClientRect().top - ANCHOR_GAP_PX;
  }, [anchored]);

  return (
    <SettingsGroup ref={group} title={t("messengers.title")}>
      <p className="text-muted-foreground text-sm">{t("messengers.description")}</p>
      {links.isPending ? <Spinner className="my-3" /> : null}
      {links.isError ? (
        <div role="alert" className="flex items-center gap-3 py-2 text-sm">
          {t("messengers.loadFailed")}
          <Button variant="outline" size="sm" onClick={() => void links.refetch()}>
            {common("actions.retry")}
          </Button>
        </div>
      ) : null}
      {links.isSuccess ? (
        <ul className="divide-y">
          {telegram ? (
            <LinkedTelegram link={telegram} onUnlinked={reset} />
          ) : (
            <LinkingTelegram flow={flow} onBegin={begin} onCancel={reset} />
          )}
          {items.map((link) => {
            if (link.messenger !== "slack") return null;
            return link.state === "proposed" ? (
              <SlackProposal key={link.id} link={link} />
            ) : (
              <SlackLinked key={link.id} link={link} />
            );
          })}
        </ul>
      ) : null}
      <p role="status" className="sr-only">
        {flow.step === "linked"
          ? t.rich("messengers.telegram.linkedAs", { account: () => <bdi>{flow.handle}</bdi> })
          : null}
      </p>
    </SettingsGroup>
  );
}
