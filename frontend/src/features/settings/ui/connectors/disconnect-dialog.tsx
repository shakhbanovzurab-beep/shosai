"use client";

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
} from "@/components/ui/alert-dialog";

import type { Connector } from "../../domain/connectors-contract";
import { disconnectConnector } from "../../model/connector-actions";

/**
 * Asks before an app is disconnected: everything in Shosai that uses it stops at once, and — while other apps
 * share the account's access or the provider can't withdraw it — the provider still lists Shosai's access.
 */
export function DisconnectDialog({ connector, onClose }: { connector: Connector | null; onClose: () => void }) {
  const t = useTranslations("settingsConnectors");
  const common = useTranslations("common");
  const name = connector?.name ?? "";

  return (
    <AlertDialog open={connector !== null} onOpenChange={(open) => (open ? undefined : onClose())}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t("disconnectDialog.title", { name })}</AlertDialogTitle>
          <AlertDialogDescription>{t("disconnectDialog.body", { name })}</AlertDialogDescription>
          {connector?.access_remains_at_provider ? (
            <AlertDialogDescription>{t("disconnectDialog.remains")}</AlertDialogDescription>
          ) : null}
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{common("actions.cancel")}</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            onClick={() => {
              if (connector) void disconnectConnector(connector, t);
            }}
          >
            {t("disconnect")}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
