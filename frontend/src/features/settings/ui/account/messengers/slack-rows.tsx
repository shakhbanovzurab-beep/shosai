"use client";

import { toast } from "sonner";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import type { MessengerLink } from "@/features/identity/domain/messenger-links-contract";
import { useMessengerLinkActions } from "@/features/identity/model/messenger-links";
import { apiErrorDescription } from "@/lib/api/error-description";

import { AccountName, LinkedStatus, MessengerRow } from "./messenger-row";
import { UnlinkButton } from "./unlink-button";

/*
 * Аккаунты Slack — по одному на пространство Slack (CF-D10). Совпадение по почте человек подтверждает сам
 * (CF-D4): «Это не я» убирает предложение, и этот аккаунт Slack больше не предлагается.
 */

export function SlackProposal({ link }: { link: MessengerLink }) {
  const t = useTranslations("settings");
  const { confirm, remove } = useMessengerLinkActions();
  const busy = confirm.isPending || remove.isPending;
  const title = t("messengers.slack.space", { space: link.space?.name ?? "" });
  const failed = (title: string) => (error: unknown) => toast.error(title, { description: apiErrorDescription(error) });

  return (
    <MessengerRow
      messenger="slack"
      title={<bdi>{title}</bdi>}
      status={t.rich("messengers.slack.proposed", { account: () => <AccountName account={link.account} /> })}
    >
      <Button
        variant="outline"
        size="sm"
        disabled={busy}
        onClick={() =>
          confirm.mutate(link.id, {
            onSuccess: () => toast.success(t("messengers.slack.confirmed")),
            onError: failed(t("messengers.slack.confirmFailed")),
          })
        }
      >
        {t("messengers.slack.confirm")}
      </Button>
      <Button
        variant="ghost"
        size="sm"
        disabled={busy}
        onClick={() => remove.mutate(link.id, { onError: failed(t("messengers.slack.notMeFailed")) })}
      >
        {t("messengers.slack.notMe")}
      </Button>
    </MessengerRow>
  );
}

export function SlackLinked({ link }: { link: MessengerLink }) {
  const t = useTranslations("settings");
  const space = link.space?.name ?? "";
  const title = t("messengers.slack.space", { space });
  return (
    <MessengerRow messenger="slack" title={<bdi>{title}</bdi>} status={<LinkedStatus link={link} />}>
      <UnlinkButton
        link={link}
        title={t("messengers.slack.unlinkTitle", { space })}
        description={t("messengers.slack.unlinkBody", { space })}
      />
    </MessengerRow>
  );
}
