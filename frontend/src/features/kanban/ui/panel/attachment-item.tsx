"use client";

import { Download, EllipsisVertical, File as FileIcon, FileText, ImageMinus, ImagePlus, Trash2 } from "lucide-react";
import { useFormatter, useLocale, useTranslations } from "use-intl";

import { Attachment, AttachmentContent, AttachmentMedia } from "@/components/ui/attachment";
import {
  AttachmentAction,
  AttachmentActions,
  AttachmentDescription,
  AttachmentTitle,
} from "@/components/ui/attachment-parts";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { DropdownMenuItem, DropdownMenuSeparator } from "@/components/ui/dropdown-menu-items";
import { formatBytes } from "@/i18n/format-units";

import type { Attachment as TaskAttachment } from "../../domain/tasks-contract";
import { useAttachmentActions } from "./use-panel-actions";

/** Превью картинки — фон: картинка декоративная, имя файла рядом. Документ — значком. */
function Preview({ attachment }: { attachment: TaskAttachment }) {
  if (attachment.preview_url)
    return (
      <AttachmentMedia variant="image">
        <div
          aria-hidden="true"
          className="size-full bg-center bg-cover"
          style={{ backgroundImage: `url("${attachment.preview_url.replace(/"/g, "%22")}")` }}
        />
      </AttachmentMedia>
    );
  return (
    <AttachmentMedia>{attachment.content_type === "application/pdf" ? <FileText /> : <FileIcon />}</AttachmentMedia>
  );
}

/** Вложение задачи: превью, имя, размер, кто и когда; меню — скачать, обложка, удалить. */
export function AttachmentItem({
  taskId,
  attachment,
  isCover,
  editable,
}: {
  taskId: string;
  attachment: TaskAttachment;
  isCover: boolean;
  editable: boolean;
}) {
  const t = useTranslations("kanbanPanel");
  const locale = useLocale();
  const format = useFormatter();
  const actions = useAttachmentActions(taskId);
  const name = attachment.name;
  const added = format.dateTime(new Date(attachment.added_at), { dateStyle: "medium" });
  return (
    <Attachment className="w-full">
      <Preview attachment={attachment} />
      <AttachmentContent>
        <AttachmentTitle>
          <bdi>{name}</bdi>
        </AttachmentTitle>
        <AttachmentDescription>
          {formatBytes(locale, attachment.size_bytes)} ·{" "}
          {t("attachments.added", { name: attachment.added_by.name, date: added })}
        </AttachmentDescription>
      </AttachmentContent>
      {isCover ? <Badge variant="secondary">{t("attachments.cover")}</Badge> : null}
      <AttachmentActions>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <AttachmentAction aria-label={t("attachments.actions", { name })}>
              <EllipsisVertical />
            </AttachmentAction>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-max min-w-44">
            <DropdownMenuGroup>
              <DropdownMenuItem
                onSelect={() => void actions.download(attachment, t("attachments.downloadFailed", { name }))}
              >
                <Download />
                {t("attachments.download")}
              </DropdownMenuItem>
              {editable && attachment.image ? (
                <DropdownMenuItem onSelect={() => void actions.setCover(isCover ? null : attachment)}>
                  {isCover ? <ImageMinus /> : <ImagePlus />}
                  {t(isCover ? "attachments.removeCover" : "attachments.makeCover")}
                </DropdownMenuItem>
              ) : null}
            </DropdownMenuGroup>
            {editable ? (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuGroup>
                  <DropdownMenuItem
                    variant="destructive"
                    onSelect={() => actions.remove(attachment, t("attachments.deleted", { name }))}
                  >
                    <Trash2 />
                    {t("attachments.delete")}
                  </DropdownMenuItem>
                </DropdownMenuGroup>
              </>
            ) : null}
          </DropdownMenuContent>
        </DropdownMenu>
      </AttachmentActions>
    </Attachment>
  );
}
