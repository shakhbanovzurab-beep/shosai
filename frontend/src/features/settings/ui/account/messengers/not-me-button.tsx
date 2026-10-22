"use client";

import { toast } from "sonner";
import { useTranslations } from "use-intl";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import type { MessengerLink } from "@/features/identity/domain/messenger-links-contract";
import { useMessengerLinkActions } from "@/features/identity/model/messenger-links";
import { apiErrorDescription } from "@/lib/api/error-description";

import { AccountName } from "./messenger-row";

/** «Это не я» с подтверждением: этот аккаунт Slack больше не предлагается, а привязать его вручную нельзя (CF-D4). */
export function NotMeButton({ link, disabled }: { link: MessengerLink; disabled: boolean }) {
  const t = useTranslations("settings");
  const common = useTranslations("common");
  const { remove } = useMessengerLinkActions();
  const refuse = () =>
    remove.mutate(link.id, {
      onError: (error) => toast.error(t("messengers.slack.notMeFailed"), { description: apiErrorDescription(error) }),
    });

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="ghost" size="sm" disabled={disabled || remove.isPending}>
          {t("messengers.slack.notMe")}
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t("messengers.slack.notMeTitle")}</AlertDialogTitle>
          <AlertDialogDescription>
            {t.rich("messengers.slack.notMeBody", {
              account: () => <AccountName account={link.account} />,
              space: () => <bdi>{link.space?.name}</bdi>,
            })}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{common("actions.cancel")}</AlertDialogCancel>
          <AlertDialogAction variant="destructive" onClick={refuse}>
            {t("messengers.slack.notMeConfirm")}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
