"use client";

import { useState, useTransition } from "react";

import { X } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

import { BODY_MAX, SUBJECT_MAX, TICKET_CATEGORIES, type TicketCategory } from "../domain/contract";
import { isTicketCategory } from "../domain/tickets";
import { useAddFiles } from "../model/attachments";
import { openTicket } from "../model/ticket-actions";
import { AttachButton, PendingFiles } from "./attachments-field";

/** "How can we help?": topic, subject, details and files; opens the new ticket when sent. */
export function NewTicketForm({ onClose }: { onClose: () => void }) {
  const t = useTranslations("pagesSupport");
  const tc = useTranslations("common");
  const addFiles = useAddFiles();
  const [category, setCategory] = useState<TicketCategory | null>(null);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [sending, startSending] = useTransition();
  const ready = category !== null && subject.trim() !== "" && body.trim() !== "";

  const submit = () =>
    startSending(async () => {
      if (!category) return;
      await openTicket(t, subject.trim(), category, body.trim(), files);
    });

  return (
    <section aria-labelledby="new-ticket-title" className="h-full min-h-0 overflow-y-auto">
      <form action={submit} className="mx-auto flex w-full max-w-2xl flex-col gap-5 p-5">
        <div className="flex items-start gap-2">
          <div className="flex flex-1 flex-col gap-1">
            <h2 id="new-ticket-title" className="font-medium text-xl">
              {t("form.title")}
            </h2>
            <p className="text-muted-foreground text-sm">{t("form.subtitle")}</p>
          </div>
          <Button type="button" variant="ghost" size="icon-sm" aria-label={tc("actions.close")} onClick={onClose}>
            <X />
          </Button>
        </div>
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-2 font-medium text-sm">{t("form.topic")}</legend>
          <ToggleGroup
            type="single"
            variant="outline"
            size="sm"
            value={category ?? ""}
            onValueChange={(v) => setCategory(isTicketCategory(v) ? v : null)}
            className="flex-wrap"
          >
            {TICKET_CATEGORIES.map((id) => (
              <ToggleGroupItem key={id} value={id} className="px-3">
                {t(`categories.${id}`)}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </fieldset>
        <div className="flex flex-col gap-2">
          <Label htmlFor="ticket-subject">{t("form.subject")}</Label>
          <Input
            id="ticket-subject"
            dir="auto"
            value={subject}
            maxLength={SUBJECT_MAX}
            onChange={(e) => setSubject(e.currentTarget.value)}
            placeholder={t("form.subjectPlaceholder")}
          />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="ticket-body">{t("form.body")}</Label>
          <Textarea
            id="ticket-body"
            dir="auto"
            value={body}
            maxLength={BODY_MAX}
            onChange={(e) => setBody(e.currentTarget.value)}
            placeholder={t("form.bodyPlaceholder")}
            className="min-h-40"
          />
        </div>
        <PendingFiles files={files} onRemove={(i) => setFiles((current) => current.filter((_, j) => j !== i))} />
        <div className="flex items-center justify-between">
          <AttachButton onAdd={(added) => setFiles((current) => addFiles(current, added))} disabled={sending} />
          <Button type="submit" disabled={!ready || sending}>
            {sending ? <Spinner data-icon="inline-start" /> : null}
            {t("form.send")}
          </Button>
        </div>
      </form>
    </section>
  );
}
