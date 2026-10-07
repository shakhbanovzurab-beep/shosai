"use client";

import {
  Archive,
  ChevronLeft,
  ChevronRight,
  EllipsisVertical,
  Forward,
  MailOpen,
  Pin,
  Reply,
  ReplyAll,
  Tag,
  Trash2,
  X,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

/** Actions above an open email: close, previous/next, pin, archive, reply, more, trash. */
export function MailViewToolbar({ onClose }: { onClose: () => void }) {
  const t = useTranslations("mail");

  return (
    <div className="flex items-center">
      <div className="flex items-center gap-2">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon-sm" aria-label={t("toolbar.close")} onClick={onClose}>
              <X />
            </Button>
          </TooltipTrigger>
          <TooltipContent>{t("toolbar.close")}</TooltipContent>
        </Tooltip>
        <Separator className="h-4 data-vertical:self-center" orientation="vertical" />
        <div className="flex items-center gap-0">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon-sm" aria-label={t("toolbar.previous")}>
                <ChevronLeft className="rtl:-scale-x-100" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>{t("toolbar.previous")}</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon-sm" aria-label={t("toolbar.next")}>
                <ChevronRight className="rtl:-scale-x-100" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>{t("toolbar.next")}</TooltipContent>
          </Tooltip>
        </div>
      </div>

      <div className="ms-auto flex items-center gap-2">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon-sm" aria-label={t("toolbar.pin")}>
              <Pin />
            </Button>
          </TooltipTrigger>
          <TooltipContent>{t("toolbar.pin")}</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon-sm" aria-label={t("menu.archive")}>
              <Archive />
            </Button>
          </TooltipTrigger>
          <TooltipContent>{t("menu.archive")}</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon-sm" aria-label={t("toolbar.reply")}>
              <Reply className="rtl:-scale-x-100" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>{t("toolbar.reply")}</TooltipContent>
        </Tooltip>
        <Tooltip>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon-sm" aria-label={t("toolbar.more")}>
                  <EllipsisVertical />
                </Button>
              </TooltipTrigger>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuGroup>
                <DropdownMenuItem>
                  <ReplyAll className="rtl:-scale-x-100" />
                  {t("toolbar.replyAll")}
                </DropdownMenuItem>
                <DropdownMenuItem>
                  <Forward className="rtl:-scale-x-100" />
                  {t("toolbar.forward")}
                </DropdownMenuItem>
              </DropdownMenuGroup>
              <DropdownMenuSeparator />
              <DropdownMenuGroup>
                <DropdownMenuItem>
                  <MailOpen />
                  {t("menu.markUnread")}
                </DropdownMenuItem>
                <DropdownMenuItem>
                  <Tag />
                  {t("toolbar.addLabel")}
                </DropdownMenuItem>
              </DropdownMenuGroup>
            </DropdownMenuContent>
          </DropdownMenu>
          <TooltipContent>{t("toolbar.more")}</TooltipContent>
        </Tooltip>
        <Separator className="h-4 data-vertical:self-center" orientation="vertical" />
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon-sm" aria-label={t("menu.trash")}>
              <Trash2 className="text-destructive" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>{t("menu.trash")}</TooltipContent>
        </Tooltip>
      </div>
    </div>
  );
}
