import { useId, useState } from "react";

import { Check, Copy, UserPlus } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput } from "@/components/ui/input-group";
import { copyText } from "@/lib/copy-text";

/** Приглашение — ссылка комнаты: по ней войдёт любой, у кого она есть. */
export function InviteDialog({ link }: { link: string }) {
  const t = useTranslations("meetingRoom");
  const id = useId();
  const [copied, setCopied] = useState(false);
  return (
    <Dialog onOpenChange={() => setCopied(false)}>
      <DialogTrigger asChild>
        <Button variant="outline" size="icon" aria-label={t("invite.open")}>
          <UserPlus aria-hidden="true" />
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("invite.title")}</DialogTitle>
          <DialogDescription>{t("invite.description")}</DialogDescription>
        </DialogHeader>
        <InputGroup>
          <InputGroupInput
            id={id}
            readOnly
            value={link}
            aria-label={t("invite.link")}
            onFocus={(event) => event.target.select()}
          />
          <InputGroupAddon align="inline-end">
            <InputGroupButton
              onClick={async () => {
                await copyText(link);
                setCopied(true);
              }}
            >
              {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
              {copied ? t("invite.copied") : t("invite.copy")}
            </InputGroupButton>
          </InputGroupAddon>
        </InputGroup>
      </DialogContent>
    </Dialog>
  );
}
