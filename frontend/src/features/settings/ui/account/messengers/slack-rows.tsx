"use client";

import { toast } from "sonner";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import type { MessengerLink } from "@/features/identity/domain/messenger-links-contract";
import { useMessengerLinkActions } from "@/features/identity/model/messenger-links";
import { apiErrorDescription } from "@/lib/api/error-description";

import { AccountName, LinkedStatus, MessengerRow } from "./messenger-row";
import { NotMeButton } from "./not-me-button";
import { UnlinkButton } from "./unlink-button";

/*
 * Аккаунты Slack — по одному на пространство Slack (CF-D10). Совпадение по почте человек подтверждает сам
 * (CF-D4) или отвечает «Это не я» (`not-me-button.tsx`).
 */

export function SlackProposal({ link }: { link: MessengerLink }) {
  const t = useTranslations("settings");
  const { confirm } = useMessengerLinkActions();
  const busy = confirm.isPending;
  const title = t("messengers.slack.space", { space: link.space?.name ?? "" });

  return (
    <MessengerRow
      messenger="slack"
      title={title}
      status={t.rich("messengers.slack.proposed", { account: () => <AccountName account={link.account} /> })}
    >
      <Button
        variant="outline"
        size="sm"
        disabled={busy}
        onClick={() =>
          confirm.mutate(link.id, {
            onSuccess: () => toast.success(t("messengers.slack.confirmed")),
            onError: (error) =>
              toast.error(t("messengers.slack.confirmFailed"), { description: apiErrorDescription(error) }),
          })
        }
      >
        {t("messengers.slack.confirm")}
      </Button>
      <NotMeButton link={link} disabled={busy} />
    </MessengerRow>
  );
}

export function SlackLinked({ link }: { link: MessengerLink }) {
  const t = useTranslations("settings");
  const space = link.space?.name ?? "";
  const title = t("messengers.slack.space", { space });
  return (
    <MessengerRow messenger="slack" title={title} status={<LinkedStatus link={link} />}>
      <UnlinkButton
        link={link}
        title={t("messengers.slack.unlinkTitle", { space })}
        description={t("messengers.slack.unlinkBody", { space })}
      />
    </MessengerRow>
  );
}
