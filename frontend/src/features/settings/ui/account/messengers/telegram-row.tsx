"use client";

import { ExternalLink } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import type { MessengerLink } from "@/features/identity/domain/messenger-links-contract";
import type { TelegramLinkFlow } from "@/features/identity/model/telegram-link";

import { LinkedStatus, MessengerRow } from "./messenger-row";
import { UnlinkButton } from "./unlink-button";

/*
 * Telegram в «Мессенджерах»: привязанный аккаунт с «Отвязать» или путь привязки — ожидание, истёкшая ссылка,
 * отказ. Состояние пути держит группа (`messengers-group.tsx`), строки только показывают его.
 */

export function LinkedTelegram({ link, onUnlinked }: { link: MessengerLink; onUnlinked: () => void }) {
  const t = useTranslations("settings");
  return (
    <MessengerRow messenger="telegram" title={t("messengers.names.telegram")} status={<LinkedStatus link={link} />}>
      <UnlinkButton
        link={link}
        title={t("messengers.telegram.unlinkTitle")}
        description={t("messengers.telegram.unlinkBody")}
        onUnlinked={onUnlinked}
      />
    </MessengerRow>
  );
}

function Waiting({ flow, onCancel }: { flow: Extract<TelegramLinkFlow, { step: "waiting" }>; onCancel: () => void }) {
  const t = useTranslations("settings");
  const common = useTranslations("common");
  return (
    <MessengerRow
      messenger="telegram"
      title={t("messengers.names.telegram")}
      status={
        <span className="flex items-start gap-1.5">
          <Spinner aria-hidden="true" className="mt-px size-3 shrink-0" />
          <span>{t.rich("messengers.telegram.waiting", { bot: () => <bdi dir="ltr">@{flow.bot}</bdi> })}</span>
        </span>
      }
    >
      <Button variant="outline" size="sm" asChild>
        <a href={flow.url} target="_blank" rel="noopener noreferrer">
          {t("messengers.telegram.openAgain")}
          <ExternalLink data-icon="inline-end" className="rtl:-scale-x-100" />
        </a>
      </Button>
      <Button variant="ghost" size="sm" onClick={onCancel}>
        {common("actions.cancel")}
      </Button>
    </MessengerRow>
  );
}

/** Ссылка истекла или аккаунт Telegram занят: сказать почему и дать начать заново. */
function Ended({ status, onBegin }: { status: string; onBegin: () => void }) {
  const t = useTranslations("settings");
  const common = useTranslations("common");
  return (
    <MessengerRow messenger="telegram" title={t("messengers.names.telegram")} status={status}>
      <Button variant="outline" size="sm" onClick={onBegin}>
        {common("actions.retry")}
      </Button>
    </MessengerRow>
  );
}

export function LinkingTelegram({
  flow,
  onBegin,
  onCancel,
}: {
  flow: TelegramLinkFlow;
  onBegin: () => void;
  onCancel: () => void;
}) {
  const t = useTranslations("settings");
  const name = t("messengers.names.telegram");
  switch (flow.step) {
    case "waiting":
      return <Waiting flow={flow} onCancel={onCancel} />;
    case "linked":
      return (
        <MessengerRow
          messenger="telegram"
          title={name}
          status={t.rich("messengers.telegram.linkedAs", { account: () => <bdi>{flow.handle}</bdi> })}
        />
      );
    case "expired":
      return <Ended status={t("messengers.telegram.expired")} onBegin={onBegin} />;
    case "refused":
      return <Ended status={t("messengers.telegram.refused")} onBegin={onBegin} />;
    default:
      return (
        <MessengerRow messenger="telegram" title={name} status={t("messengers.notLinked")}>
          <Button variant="outline" size="sm" disabled={flow.step === "starting"} onClick={onBegin}>
            {flow.step === "starting" ? <Spinner aria-hidden="true" data-icon="inline-start" /> : null}
            {t("messengers.telegram.link")}
          </Button>
        </MessengerRow>
      );
  }
}
