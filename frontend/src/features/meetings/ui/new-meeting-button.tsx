"use client";

import Link from "next/link";

import { CalendarPlus, ChevronDown, Plus, Upload } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

/**
 * Meetings are planned in Calendar and recordings are added in Notes, so the primary action hands off
 * to them rather than duplicating either here.
 */
export function NewMeetingButton() {
  const t = useTranslations("meetings");
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button>
          <Plus data-icon="inline-start" />
          {t("newMeeting")}
          <ChevronDown data-icon="inline-end" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuItem asChild>
          <Link href="/app/calendar">
            <CalendarPlus />
            {t("actions.schedule")}
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link href="/app/notes">
            <Upload />
            {t("actions.upload")}
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
