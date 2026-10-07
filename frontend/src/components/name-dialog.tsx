"use client";

import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export type NameRequest = {
  title: string;
  initial: string;
  submitLabel: string;
  onSubmit: (name: string) => void;
};

/** Asks for a file or folder name. Opens whenever `request` is set. */
export function NameDialog({ request, onClose }: { request: NameRequest | null; onClose: () => void }) {
  const t = useTranslations("common");
  return (
    <Dialog open={request !== null} onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="sm:max-w-sm">
        {request ? (
          <form
            className="flex flex-col gap-4"
            action={(formData) => {
              const name = String(formData.get("name") ?? "").trim();
              if (!name) return;
              request.onSubmit(name);
              onClose();
            }}
          >
            <DialogHeader>
              <DialogTitle>{request.title}</DialogTitle>
            </DialogHeader>
            <div className="flex flex-col gap-2">
              <Label htmlFor="item-name">{t("fields.name")}</Label>
              <Input
                id="item-name"
                name="name"
                defaultValue={request.initial}
                required
                autoComplete="off"
                onFocus={(event) => {
                  // Select the name without its extension, the part people usually change.
                  const dot = event.currentTarget.value.lastIndexOf(".");
                  event.currentTarget.setSelectionRange(0, dot > 0 ? dot : event.currentTarget.value.length);
                }}
              />
            </div>
            <DialogFooter>
              <DialogClose asChild>
                <Button type="button" variant="outline">
                  {t("actions.cancel")}
                </Button>
              </DialogClose>
              <Button type="submit">{request.submitLabel}</Button>
            </DialogFooter>
          </form>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
