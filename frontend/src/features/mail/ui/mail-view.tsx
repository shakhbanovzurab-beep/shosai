"use client";

import type { ReactNode } from "react";

import { cn } from "cn";
import { ChevronDown } from "lucide-react";
import { siFigma, siGoogledocs, siGooglephotos } from "simple-icons";
import { useFormatter, useLocale, useTranslations } from "use-intl";

import { SimpleIcon } from "@/components/simple-icon";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Separator } from "@/components/ui/separator";
import { formatBytes } from "@/i18n/format-units";

import type { AttachmentKind, Mail } from "../domain/mail";
import { useLeoInbox } from "../model/leo-insights";
import { useMail } from "../model/use-mail";
import { LeoDraft } from "./leo-draft";
import { LeoMailCard } from "./leo-mail-card";
import { MailReplyBar } from "./mail-reply-bar";
import { MailViewToolbar } from "./mail-view-toolbar";
import { useMailDates } from "./use-mail-dates";

const ATTACHMENT_ICONS: Record<AttachmentKind, typeof siFigma> = {
  figma: siFigma,
  document: siGoogledocs,
  image: siGooglephotos,
};

interface MailDisplayProps {
  mail: Mail | null;
  onClose?: () => void;
}

export function MailView({ mail, onClose }: MailDisplayProps) {
  const t = useTranslations("mail");
  const format = useFormatter();
  const locale = useLocale();
  const { timestamp } = useMailDates();
  const [, setMail] = useMail();
  const names = (recipients: { name: string }[]) => format.list(recipients.map((recipient) => recipient.name));
  const nameTag = (chunks: ReactNode) => (
    <span dir="auto" className="text-foreground">
      {chunks}
    </span>
  );
  const { state, views } = useLeoInbox();
  const view = mail ? views.get(mail.id) : undefined;
  const draft = view?.draft ?? null;

  function handleClose() {
    setMail({ selected: null });
    onClose?.();
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 px-2 py-3">
      <MailViewToolbar onClose={handleClose} />

      <Separator />

      <div className="flex min-h-0 flex-1 flex-col">
        {mail ? (
          <div className="flex min-h-0 flex-1 flex-col gap-3">
            <div className="space-y-1.5">
              <div dir="auto" className="font-medium leading-none">
                {mail.subject}
              </div>

              <div className="text-muted-foreground text-xs leading-none">{timestamp(mail.receivedAt)}</div>
            </div>

            <Separator />

            <div className="flex gap-2">
              <Avatar className="size-9 after:rounded-sm">
                <AvatarFallback className="rounded-sm bg-background">{mail.from.name[0]}</AvatarFallback>
              </Avatar>

              <div className="flex h-full flex-col gap-1">
                <div className="flex items-center gap-2">
                  <div dir="auto" className="text-xs">
                    {mail.from.name}
                  </div>
                  <Separator className="h-3 data-vertical:self-center" orientation="vertical" />
                  <div className="text-muted-foreground text-xs">{mail.from.email}</div>
                </div>
                <div className="flex items-center gap-2">
                  <div className="text-muted-foreground text-xs">
                    {t.rich("reader.to", { names: nameTag, list: names(mail.to) })}
                  </div>

                  {mail.cc?.length ? (
                    <div className="text-muted-foreground text-xs">
                      {t.rich("reader.cc", { names: nameTag, list: names(mail.cc) })}
                    </div>
                  ) : null}
                </div>
              </div>
            </div>

            <Separator />

            {/* The column inside grows with its content, so nothing in it is squeezed; the outer box scrolls. */}
            <div className="scrollbar-none min-h-0 flex-1 overflow-y-auto">
              <div className="flex flex-col gap-3">
                <LeoMailCard mail={mail} state={state} view={view} />

                {mail.attachments?.length ? (
                  <>
                    <Collapsible defaultOpen>
                      <CollapsibleTrigger asChild>
                        <Button
                          variant="ghost"
                          size="sm"
                          className={cn(
                            "group p-0 font-normal text-muted-foreground",
                            "hover:bg-transparent hover:text-muted-foreground dark:hover:bg-transparent",
                            "data-[state=open]:bg-transparent data-[state=open]:text-muted-foreground",
                          )}
                        >
                          {t("reader.attachments", { count: mail.attachments.length })}
                          <ChevronDown className="group-data-[state=open]:rotate-180" />
                        </Button>
                      </CollapsibleTrigger>

                      <CollapsibleContent>
                        <div className="flex flex-wrap gap-2">
                          {mail.attachments.map((attachment) => (
                            <Button size="xs" variant="secondary" key={attachment.id}>
                              <SimpleIcon icon={ATTACHMENT_ICONS[attachment.kind]} className="size-3 fill-current" />
                              <span dir="auto" className="font-normal">
                                {attachment.name}
                              </span>
                              <span className="font-normal text-muted-foreground">
                                {formatBytes(locale, attachment.size)}
                              </span>
                            </Button>
                          ))}
                        </div>
                      </CollapsibleContent>
                    </Collapsible>

                    <Separator className="my-2" />
                  </>
                ) : null}

                <div dir="auto" className="whitespace-pre-wrap text-sm">
                  {mail.body}
                </div>
              </div>
            </div>

            <div className="mt-auto flex flex-col gap-3">
              <Separator />
              {draft !== null && !mail.repliedAt ? (
                <LeoDraft key={mail.id} mail={mail} draft={draft} />
              ) : (
                <MailReplyBar key={mail.id} mail={mail} />
              )}
            </div>
          </div>
        ) : (
          <div className="grid h-full place-items-center text-muted-foreground text-sm">{t("inbox.noSelection")}</div>
        )}
      </div>
    </div>
  );
}
