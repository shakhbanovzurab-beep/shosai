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

/** «Отвязать» с подтверждением: что перестанет работать, говорит тот, кто ставит кнопку. */
export function UnlinkButton({
  link,
  title,
  description,
  onUnlinked,
}: {
  link: MessengerLink;
  title: string;
  description: string;
  onUnlinked?: () => void;
}) {
  const t = useTranslations("settings");
  const common = useTranslations("common");
  const { remove } = useMessengerLinkActions();
  const name = t(`messengers.names.${link.messenger}`);

  const unlink = () =>
    remove.mutate(link.id, {
      onSuccess: () => {
        onUnlinked?.();
        toast.success(t("messengers.unlinked", { messenger: name }));
      },
      onError: (error) => toast.error(t("messengers.unlinkFailed"), { description: apiErrorDescription(error) }),
    });

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="outline" size="sm" disabled={remove.isPending}>
          {t("messengers.unlink")}
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{common("actions.cancel")}</AlertDialogCancel>
          <AlertDialogAction variant="destructive" onClick={unlink}>
            {t("messengers.unlink")}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
