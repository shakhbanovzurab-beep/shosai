"use client";

import * as React from "react";

import { FileText, Plus, X } from "lucide-react";
import { useLocale, useTranslations } from "use-intl";

import { Attachment, AttachmentContent, AttachmentMedia } from "@/components/ui/attachment";
import {
  AttachmentAction,
  AttachmentActions,
  AttachmentDescription,
  AttachmentGroup,
  AttachmentTitle,
} from "@/components/ui/attachment-parts";
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupTextarea } from "@/components/ui/input-group";
import { formatBytes } from "@/i18n/format-units";

import { LEO_MAX_ATTACHMENTS } from "../domain/attachments";
import type { useLeoAttachments } from "../model/use-leo-attachments";
import { type ComposerAction, LeoComposerAction } from "./leo-composer-action";

// One line of text (24px) plus the field's vertical padding (16px), with a little slack.
const SINGLE_LINE_HEIGHT = 44;

interface LeoComposerProps {
  readonly isBusy: boolean;
  readonly attachments: ReturnType<typeof useLeoAttachments>;
  readonly onSend: (content: string, files: File[]) => void;
  readonly onStop: () => void;
  readonly onStartVoice: () => void;
  /** Settings › Leo › Voice mode; when off, there is no voice button at all. */
  readonly voiceEnabled: boolean;
  /** A line under the input saying where Leo's answers stop, e.g. inside one hub. */
  readonly caption?: string | null;
  /** Текст, с которым поле открывается, например вопрос из ⌘K, пока Leo отвечал. */
  readonly initialValue?: string;
}

export function LeoComposer({
  isBusy,
  attachments,
  onSend,
  onStop,
  onStartVoice,
  voiceEnabled,
  caption,
  initialValue = "",
}: LeoComposerProps) {
  const t = useTranslations("leo");
  const locale = useLocale();
  const { files, addFiles, removeFile, clearFiles } = attachments;
  const [value, setValue] = React.useState(initialValue);
  // Single row while the text fits on one line; once it wraps, the text takes the full width above the buttons.
  // Like ChatGPT it stays that way until the field is cleared.
  const [isMultiline, setIsMultiline] = React.useState(false);
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const hasDraft = value.trim().length > 0 || files.length > 0;
  const canSend = !isBusy && hasDraft;
  // Like ChatGPT: voice mode by default, Send once there is something to send, Stop while Leo works.
  // With voice mode switched off in Settings, Send takes its place (disabled until there's a draft).
  let primaryAction: ComposerAction = voiceEnabled ? "voice" : "send";
  if (isBusy) primaryAction = "stop";
  else if (hasDraft) primaryAction = "send";

  React.useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  const submit = () => {
    if (!canSend) return;
    onSend(
      value.trim(),
      files.map((f) => f.file),
    );
    setValue("");
    setIsMultiline(false);
    clearFiles();
  };

  return (
    <form
      className="flex flex-col gap-2 px-3 pt-1 pb-2 group-data-[expanded=true]/leo:mx-auto group-data-[expanded=true]/leo:w-full group-data-[expanded=true]/leo:max-w-3xl"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      {files.length > 0 ? (
        <AttachmentGroup className="w-full px-1" aria-label={t("composer.filesToSend")}>
          {files.map(({ id, file }) => (
            <Attachment key={id} size="xs" className="min-w-0 max-w-48">
              <AttachmentMedia>
                <FileText />
              </AttachmentMedia>
              <AttachmentContent>
                <AttachmentTitle>{file.name}</AttachmentTitle>
                <AttachmentDescription>{formatBytes(locale, file.size)}</AttachmentDescription>
              </AttachmentContent>
              <AttachmentActions>
                <AttachmentAction
                  aria-label={t("composer.removeFile", { name: file.name })}
                  onClick={() => removeFile(id)}
                >
                  <X />
                </AttachmentAction>
              </AttachmentActions>
            </Attachment>
          ))}
        </AttachmentGroup>
      ) : null}
      {/* One row like ChatGPT: attach, the message, then voice / send / stop; buttons stay on the last line. */}
      <InputGroup data-multiline={isMultiline} className="flex-wrap items-center rounded-3xl px-1">
        <InputGroupAddon
          align="inline-start"
          className="py-1 group-data-[multiline=true]/input-group:order-2 group-data-[multiline=true]/input-group:pt-0"
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="sr-only"
            tabIndex={-1}
            aria-hidden="true"
            onChange={(event) => {
              if (event.target.files) addFiles(event.target.files);
              event.target.value = "";
            }}
          />
          <InputGroupButton
            type="button"
            size="icon-sm"
            className="rounded-full"
            aria-label={t("composer.attach")}
            title={t("composer.attachLimit", { max: LEO_MAX_ATTACHMENTS })}
            disabled={files.length >= LEO_MAX_ATTACHMENTS}
            onClick={() => fileInputRef.current?.click()}
          >
            <Plus />
          </InputGroupButton>
        </InputGroupAddon>
        <InputGroupTextarea
          ref={textareaRef}
          value={value}
          onChange={(event) => {
            const next = event.target.value;
            setValue(next);
            if (!next) setIsMultiline(false);
            else if (event.target.scrollHeight > SINGLE_LINE_HEIGHT) setIsMultiline(true);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              submit();
            }
          }}
          onPaste={(event) => {
            if (event.clipboardData.files.length === 0) return;
            event.preventDefault();
            addFiles(event.clipboardData.files);
          }}
          placeholder={t("composer.placeholder")}
          aria-label={t("composer.label")}
          maxLength={4000}
          rows={1}
          className="max-h-40 min-h-10 flex-1 px-1 py-2 text-sm leading-6 group-data-[multiline=true]/input-group:order-1 group-data-[multiline=true]/input-group:basis-full group-data-[multiline=true]/input-group:px-2.5 group-data-[multiline=true]/input-group:pt-3 group-data-[multiline=true]/input-group:pb-0"
        />
        <InputGroupAddon
          align="inline-end"
          className="py-1 group-data-[multiline=true]/input-group:order-3 group-data-[multiline=true]/input-group:ms-auto group-data-[multiline=true]/input-group:pt-0"
        >
          <LeoComposerAction action={primaryAction} canSend={canSend} onStop={onStop} onStartVoice={onStartVoice} />
        </InputGroupAddon>
      </InputGroup>
      {caption ? <p className="text-center font-medium text-[11px] text-foreground/80">{caption}</p> : null}
      <p className="text-center text-[11px] text-muted-foreground">{t("composer.disclaimer")}</p>
    </form>
  );
}
