"use client";

import { useState, useTransition } from "react";

import { useTranslations } from "use-intl";

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";

import { deleteAccount } from "../../model/account-actions";
import { SettingsGroup, SettingsRow } from "../settings-row";

/** The last thing in Account: delete everything, confirmed by retyping the account's email. */
export function DeleteAccount({ email }: { email: string }) {
  const t = useTranslations("settings");
  const common = useTranslations("common");
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [deleting, startDeleting] = useTransition();
  const matches = typed.trim().toLowerCase() === email.toLowerCase();

  const remove = () => startDeleting(() => deleteAccount(typed.trim(), t));

  return (
    <SettingsGroup title={t("deleteAccount.group")}>
      <SettingsRow title={t("deleteAccount.title")} description={t("deleteAccount.description")}>
        <Button variant="destructive" onClick={() => setOpen(true)}>
          {t("deleteAccount.title")}
        </Button>
      </SettingsRow>
      <AlertDialog
        open={open}
        onOpenChange={(next) => {
          setOpen(next);
          if (!next) setTyped("");
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("deleteAccount.confirmTitle")}</AlertDialogTitle>
            <AlertDialogDescription>{t("deleteAccount.confirmDescription")}</AlertDialogDescription>
          </AlertDialogHeader>
          <div className="flex flex-col gap-2">
            <Label htmlFor="delete-confirm-email">
              {t.rich("deleteAccount.confirmLabel", {
                email,
                address: (chunks) => (
                  <span dir="auto" className="font-mono">
                    {chunks}
                  </span>
                ),
              })}
            </Label>
            <Input
              id="delete-confirm-email"
              type="email"
              dir="auto"
              autoComplete="off"
              value={typed}
              onChange={(event) => setTyped(event.currentTarget.value)}
            />
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel>{common("actions.cancel")}</AlertDialogCancel>
            <Button variant="destructive" disabled={!matches || deleting} onClick={remove}>
              {deleting ? <Spinner data-icon="inline-start" /> : null}
              {t("deleteAccount.title")}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </SettingsGroup>
  );
}
